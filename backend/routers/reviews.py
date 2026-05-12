import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import require_operator
from database import get_db
from models import Client, Content
from schemas import ContentResponse, ReviewRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["reviews"], dependencies=[Depends(require_operator)])

ACTION_TO_STATUS = {
    "approve": "APPROVED",
    "remove": "REMOVED",
    "hold": "HELD",
    "monitor": "MONITORED",
}


async def _fire_webhook(url: str, payload: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.post(url, json=payload)
        logger.info("웹훅 발송 완료: url=%s status=%d", url, resp.status_code)
    except Exception as e:
        logger.warning("웹훅 발송 실패: url=%s error=%s", url, e)


@router.post("/reviews/{content_id}", response_model=ContentResponse)
def review_content(
    content_id: str,
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
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

    if record.client_id:
        client = db.query(Client).filter(Client.id == record.client_id).first()
        if client and client.webhook_url:
            background_tasks.add_task(_fire_webhook, client.webhook_url, {
                "content_id": record.content_id,
                "review_status": record.review_status,
                "review_action": record.review_action,
                "reviewed_at": record.reviewed_at.isoformat(),
            })

    return record
