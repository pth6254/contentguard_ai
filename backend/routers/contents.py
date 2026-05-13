import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import require_operator
from database import get_db
from models import Content, ModelPrediction
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
    return StatsResponse(total=total, by_status=by_status, by_level=by_level)


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
def get_predictions(content_id: str, db: Session = Depends(get_db)):
    if not db.query(Content).filter(Content.content_id == content_id).first():
        raise HTTPException(
            status_code=404,
            detail=f"content_id '{content_id}' 를 찾을 수 없습니다.",
        )
    return (
        db.query(ModelPrediction)
        .filter(ModelPrediction.content_id == content_id)
        .order_by(ModelPrediction.is_selected.desc(), ModelPrediction.created_at)
        .all()
    )


@router.get("/contents/{content_id}", response_model=ContentResponse)
def get_content(content_id: str, db: Session = Depends(get_db)):
    record = db.query(Content).filter(Content.content_id == content_id).first()
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"content_id '{content_id}' 를 찾을 수 없습니다.",
        )
    return record


@router.delete("/contents/{content_id}", status_code=204)
def delete_content(content_id: str, db: Session = Depends(get_db)):
    record = db.query(Content).filter(Content.content_id == content_id).first()
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"content_id '{content_id}' 를 찾을 수 없습니다.",
        )
    db.query(ModelPrediction).filter(ModelPrediction.content_id == content_id).delete()
    db.delete(record)
    db.commit()
    logger.info("콘텐츠 삭제: content_id=%s", content_id)
