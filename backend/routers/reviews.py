import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import require_operator
from database import get_db
from models import Content
from schemas import ContentResponse, ReviewRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["reviews"], dependencies=[Depends(require_operator)])

ACTION_TO_STATUS = {
    "approve": "APPROVED",
    "remove": "REMOVED",
    "hold": "HELD",
    "monitor": "MONITORED",
}


@router.post("/reviews/{content_id}", response_model=ContentResponse)
def review_content(
    content_id: str,
    request: ReviewRequest,
    db: Session = Depends(get_db),
):
    record = db.query(Content).filter(Content.content_id == content_id).first()
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"content_id '{content_id}' 를 찾을 수 없습니다.",
        )

    record.review_action = request.action
    record.review_status = ACTION_TO_STATUS[request.action]
    record.reviewer_comment = request.comment
    record.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(record)

    logger.info(
        "Review saved — content_id=%s action=%s status=%s",
        content_id,
        request.action,
        record.review_status,
    )
    return record
