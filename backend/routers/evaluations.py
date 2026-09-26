"""Human supplied labels and measured analysis quality."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import require_operator
from database import get_db
from models import Content, EvaluationLabel, Operator
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
    confusion = {level: {predicted: 0 for predicted in LEVELS} for level in LEVELS}
    by_category: dict[str, dict[str, int]] = {}
    evaluated = skipped = correct = tp = fp = fn = 0
    for label, content in rows:
        if (content.explanation_json or {}).get("analysis_status") != "completed":
            skipped += 1
            continue
        evaluated += 1
        actual, predicted = label.expected_level, content.risk_level
        if actual not in LEVELS or predicted not in LEVELS:
            skipped += 1
            evaluated -= 1
            continue
        confusion[actual][predicted] += 1
        match = actual == predicted
        correct += int(match)
        category = label.category or "미분류"
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
