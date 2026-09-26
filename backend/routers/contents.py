import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from auth import require_operator
from database import get_db
from models import AnalysisJob, AnalysisRun, Content, EvaluationLabel, ModelPrediction
from services.content_lookup import find_content
from schemas import ContentResponse, ModelPredictionResponse, StatsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["contents"], dependencies=[Depends(require_operator)])


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    status_rows = db.query(Content.review_status, func.count()).group_by(Content.review_status).all()
    level_rows  = db.query(Content.risk_level,    func.count()).group_by(Content.risk_level).all()
    by_status   = {row[0]: row[1] for row in status_rows}
    by_level    = {row[0]: row[1] for row in level_rows}
    total       = sum(by_status.values())
    re_review = db.query(func.count(Content.id)).filter(Content.needs_re_review.is_(True)).scalar() or 0
    return StatsResponse(total=total, by_status=by_status, by_level=by_level, re_review_required=re_review)


@router.get("/contents", response_model=List[ContentResponse])
def get_contents(
    response: Response,
    status: Optional[str] = Query(None, example="PENDING"),
    risk_level: Optional[str] = Query(None, example="CRITICAL"),
    sort_by: Optional[str] = Query(None, example="risk_score"),
    search: Optional[str] = Query(None, example="사기"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Content)
    if status:
        if status.upper() == "PENDING":
            query = query.filter(or_(Content.review_status == "PENDING", Content.needs_re_review.is_(True)))
        else:
            query = query.filter(Content.review_status == status.upper())
    if risk_level:
        query = query.filter(Content.risk_level == risk_level.upper())
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            Content.text.ilike(pattern) | Content.content_id.ilike(pattern)
        )
    if sort_by == "risk_score":
        query = query.order_by(Content.risk_score.desc())
    else:
        query = query.order_by(Content.created_at.desc())

    total = query.count()
    response.headers["X-Total-Count"] = str(total)
    return query.offset(offset).limit(limit).all()


@router.get("/contents/{content_id}/predictions", response_model=List[ModelPredictionResponse])
def get_predictions(content_id: str, record_id: Optional[int] = None, db: Session = Depends(get_db)):
    record = find_content(db, content_id, record_id)
    return (db.query(ModelPrediction).filter(ModelPrediction.content_record_id == record.id)
            .order_by(ModelPrediction.is_selected.desc(), ModelPrediction.created_at).all())


@router.get("/contents/{content_id}", response_model=ContentResponse)
def get_content(content_id: str, record_id: Optional[int] = None, db: Session = Depends(get_db)):
    return find_content(db, content_id, record_id)


@router.get("/contents/{content_id}/analyses")
def get_analysis_history(content_id: str, record_id: Optional[int] = None, db: Session = Depends(get_db)):
    record = find_content(db, content_id, record_id)
    runs = (db.query(AnalysisRun).filter(AnalysisRun.content_record_id == record.id)
            .order_by(AnalysisRun.id.desc()).limit(100).all())
    return [{"id": run.id, "source": run.source, "status": run.status,
             "risk_score": run.risk_score, "risk_level": run.risk_level,
             "provider": run.provider, "model": run.model, "prompt_version": run.prompt_version,
             "policy_version": run.policy_version, "latency_ms": run.latency_ms,
             "category_scores": run.category_scores, "explanation_json": run.explanation_json,
             "created_at": run.created_at} for run in runs]


@router.delete("/contents/{content_id}", status_code=204)
def delete_content(content_id: str, record_id: Optional[int] = None, db: Session = Depends(get_db)):
    record = find_content(db, content_id, record_id)
    if db.query(AnalysisJob).filter(AnalysisJob.content_record_id == record.id,
                                    AnalysisJob.status.in_(["PENDING", "PROCESSING"])).first():
        raise HTTPException(status_code=409, detail="분석 작업이 진행 중입니다. 완료 또는 취소 후 삭제하세요.")
    db.query(AnalysisJob).filter(AnalysisJob.content_record_id == record.id).delete()
    db.query(EvaluationLabel).filter(EvaluationLabel.content_record_id == record.id).delete()
    db.query(AnalysisRun).filter(AnalysisRun.content_record_id == record.id).delete()
    db.query(ModelPrediction).filter(ModelPrediction.content_record_id == record.id).delete()
    db.delete(record)
    db.commit()
    logger.info("Content deleted: record_id=%s", record.id)
