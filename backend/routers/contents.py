import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Content
from schemas import ContentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["contents"])


@router.get("/contents", response_model=List[ContentResponse])
def get_contents(
    status: Optional[str] = Query(None, example="PENDING"),
    db: Session = Depends(get_db),
):
    query = db.query(Content)
    if status:
        query = query.filter(Content.review_status == status.upper())
    records = query.order_by(Content.created_at.desc()).all()
    return records


@router.get("/contents/{content_id}", response_model=ContentResponse)
def get_content(content_id: str, db: Session = Depends(get_db)):
    record = db.query(Content).filter(Content.content_id == content_id).first()
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"content_id '{content_id}' 를 찾을 수 없습니다.",
        )
    return record
