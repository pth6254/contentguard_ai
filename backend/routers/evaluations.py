"""Human supplied labels and measured analysis quality."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import require_operator
from database import get_db
from models import AnalysisRun, Content, EvaluationDataset, EvaluationLabel, EvaluationReport, Operator
from services.rule_detector import mask_pii

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"], dependencies=[Depends(require_operator)])
LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


class LabelRequest(BaseModel):
    expected_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    category: str | None = Field(None, max_length=40)
    reason: str | None = Field(None, max_length=1000)


@router.get("/labels/{record_id}")
def get_label(record_id: int, db: Session = Depends(get_db)):
    if not db.get(Content, record_id):
        raise HTTPException(status_code=404, detail="콘텐츠가 없습니다.")
    label = db.query(EvaluationLabel).filter(EvaluationLabel.content_record_id == record_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="평가 정답이 없습니다.")
    return {"content_record_id": record_id, "expected_level": label.expected_level,
            "category": label.category, "reason": label.reason,
            "operator_id": label.operator_id, "updated_at": label.updated_at}


@router.put("/labels/{record_id}")
def put_label(record_id: int, body: LabelRequest, db: Session = Depends(get_db),
              operator: Operator | None = Depends(require_operator)):
    record = db.query(Content).filter(Content.id == record_id).with_for_update().first()
    if not record:
        raise HTTPException(status_code=404, detail="콘텐츠가 없습니다.")
    label = db.query(EvaluationLabel).filter(EvaluationLabel.content_record_id == record_id).first()
    if not label:
        label = EvaluationLabel(content_record_id=record_id)
        db.add(label)
    label.expected_level = body.expected_level
    label.category = body.category.strip() or None if body.category else None
    label.reason = mask_pii(body.reason)[0] if body.reason else None
    label.operator_id = operator.id if operator else None
    label.updated_at = datetime.utcnow()
    db.commit()
    return get_label(record_id, db)


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    rows = (db.query(EvaluationLabel, Content).join(Content, Content.id == EvaluationLabel.content_record_id)
            .order_by(EvaluationLabel.id).all())
    return _metrics([{"actual": label.expected_level, "predicted": content.risk_level,
                     "status": (content.explanation_json or {}).get("analysis_status"),
                     "category": label.category} for label, content in rows])


def _metrics(rows):
    confusion = {level: {predicted: 0 for predicted in LEVELS} for level in LEVELS}
    by_category: dict[str, dict[str, int]] = {}
    evaluated = skipped = correct = tp = fp = fn = 0
    for row in rows:
        if row["status"] != "completed":
            skipped += 1
            continue
        evaluated += 1
        actual, predicted = row["actual"], row["predicted"]
        if actual not in LEVELS or predicted not in LEVELS:
            skipped += 1
            evaluated -= 1
            continue
        confusion[actual][predicted] += 1
        match = actual == predicted
        correct += int(match)
        category = row["category"] or "미분류"
        bucket = by_category.setdefault(category, {"total": 0, "correct": 0})
        bucket["total"] += 1
        bucket["correct"] += int(match)
        positive_actual = actual in ("HIGH", "CRITICAL")
        positive_predicted = predicted in ("HIGH", "CRITICAL")
        tp += int(positive_actual and positive_predicted)
        fp += int(not positive_actual and positive_predicted)
        fn += int(positive_actual and not positive_predicted)
    return {"labeled": len(rows), "evaluated": evaluated, "skipped": skipped,
            "accuracy": correct / evaluated if evaluated else None,
            "precision_high": tp / (tp + fp) if tp + fp else None,
            "recall_high": tp / (tp + fn) if tp + fn else None,
            "false_positives": fp, "false_negatives": fn,
            "confusion": confusion, "by_category": by_category}


class DatasetRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    client_id: int | None = Field(None, ge=1)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("이름을 입력하세요.")
        return value.strip()


class ReportRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider: str | None = Field(None, max_length=32)
    model: str | None = Field(None, max_length=100)
    prompt_version: str | None = Field(None, max_length=32)
    policy_version: str | None = Field(None, max_length=32)


@router.post("/datasets", status_code=201)
def freeze_dataset(body: DatasetRequest, db: Session = Depends(get_db)):
    query = db.query(EvaluationLabel).join(Content, Content.id == EvaluationLabel.content_record_id)
    if body.client_id:
        query = query.filter(Content.client_id == body.client_id)
    labels = query.order_by(EvaluationLabel.id).limit(10001).all()
    if not labels:
        raise HTTPException(status_code=422, detail="먼저 평가 정답을 등록하세요.")
    if len(labels) > 10000:
        raise HTTPException(status_code=422, detail="데이터셋은 최대 10,000건입니다. 고객을 선택해 범위를 줄이세요.")
    dataset = EvaluationDataset(name=body.name, items=[{"record_id": label.content_record_id,
        "expected_level": label.expected_level, "category": label.category} for label in labels])
    db.add(dataset)
    db.commit()
    return {"id": dataset.id, "name": dataset.name, "size": len(dataset.items), "created_at": dataset.created_at}


@router.get("/datasets")
def list_datasets(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    rows = db.query(EvaluationDataset).order_by(EvaluationDataset.id.desc()).offset(offset).limit(limit).all()
    return [{"id": row.id, "name": row.name, "size": len(row.items), "created_at": row.created_at} for row in rows]


def _report(row):
    return {"id": row.id, "dataset_id": row.dataset_id, "name": row.name,
            "filters": row.filters, "run_ids": row.run_ids, "metrics": row.metrics, "created_at": row.created_at}


@router.post("/datasets/{dataset_id}/reports", status_code=201)
def freeze_report(dataset_id: int, body: ReportRequest, db: Session = Depends(get_db)):
    dataset = db.get(EvaluationDataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="평가 데이터셋이 없습니다.")
    filters = {key: value for key, value in body.model_dump(exclude={"name"}).items() if value}
    query = db.query(func.max(AnalysisRun.id).label("id")).filter(
        AnalysisRun.content_record_id.in_([item["record_id"] for item in dataset.items]))
    for key, value in filters.items():
        query = query.filter(getattr(AnalysisRun, key) == value)
    selected = query.group_by(AnalysisRun.content_record_id).subquery()
    runs = db.query(AnalysisRun.id, AnalysisRun.content_record_id, AnalysisRun.risk_level, AnalysisRun.status).join(
        selected, AnalysisRun.id == selected.c.id).all()
    by_record = {run.content_record_id: run for run in runs}
    rows = []
    for item in dataset.items:
        run = by_record.get(item["record_id"])
        rows.append({"actual": item["expected_level"], "category": item["category"],
                     "predicted": run.risk_level if run else None, "status": run.status if run else "missing"})
    report = EvaluationReport(dataset_id=dataset.id, name=body.name.strip(), filters=filters,
                              run_ids=[run.id for run in runs], metrics=_metrics(rows))
    db.add(report)
    db.commit()
    return _report(report)


@router.get("/datasets/{dataset_id}/reports")
def list_reports(dataset_id: int, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db)):
    rows = db.query(EvaluationReport).filter(EvaluationReport.dataset_id == dataset_id).order_by(
        EvaluationReport.id.desc()).offset(offset).limit(limit).all()
    return [_report(row) for row in rows]
