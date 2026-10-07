import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import require_operator
from database import get_db
from models import Client, Content, Operator, ReviewEvent, WebhookDelivery
from schemas import ContentResponse, ReviewRequest
from services.content_lookup import find_content
from services.rule_detector import mask_pii

router = APIRouter(prefix="/api", tags=["reviews"])
ACTION_TO_STATUS = {"approve": "APPROVED", "remove": "REMOVED", "hold": "HELD", "monitor": "MONITORED"}


@router.post("/reviews/{content_id}", response_model=ContentResponse)
def review_content(content_id: str, request: ReviewRequest, record_id: int | None = None,
                   db: Session = Depends(get_db), operator: Operator | None = Depends(require_operator)):
    record = find_content(db, content_id, record_id, lock=True)
    version = record.review_version
    if (request.expected_analysis_version is not None and request.expected_analysis_version != record.analysis_version) or (
        request.expected_analysis_version is None and record.analysis_version > 1
    ):
        raise HTTPException(status_code=409, detail="분석 결과가 변경되었습니다. 새 결과를 확인한 후 다시 심사하세요.")
    if request.expected_version is not None and request.expected_version != version:
        raise HTTPException(status_code=409, detail="다른 운영자가 심사를 변경했습니다. 새로고침 후 다시 확인하세요.")
    now = datetime.utcnow()
    comment = mask_pii(request.comment)[0] if request.comment else None
    event = ReviewEvent(content_record_id=record.id, content_id=record.content_id,
                        client_id=record.client_id, operator_id=operator.id if operator else None,
                        actor=f"operator:{operator.id}" if operator else "legacy-admin-secret",
                        previous_status=record.review_status, previous_action=record.review_action,
                        previous_comment=mask_pii(record.reviewer_comment)[0] if record.reviewer_comment else None,
                        action=request.action, status=ACTION_TO_STATUS[request.action], comment=comment,
                        version=version + 1, analysis_version=record.analysis_version, created_at=now)
    changed = db.query(Content).filter(Content.id == record.id, Content.review_version == version).update({
        Content.review_action: request.action, Content.review_status: event.status,
        Content.reviewer_comment: comment, Content.reviewed_at: now,
        Content.review_version: version + 1,
        Content.needs_re_review: False,
    }, synchronize_session=False)
    if changed != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="심사 상태가 변경되었습니다. 다시 조회하세요.")
    db.add(event)
    db.flush()
    client = db.get(Client, record.client_id) if record.client_id else None
    if client and client.webhook_url:
        event_id = secrets.token_hex(16)
        body = json.dumps({"event_id": event_id, "content_id": record.content_id,
                           "review_status": event.status, "review_action": request.action,
                           "review_version": event.version,
                           "reviewed_at": now.replace(tzinfo=timezone.utc).isoformat()},
                          ensure_ascii=False, separators=(",", ":"))
        db.add(WebhookDelivery(id=event_id, review_event_id=event.id, url=client.webhook_url,
                               secret=client.webhook_secret, body=body))
    db.commit()
    db.refresh(record)
    return record


@router.get("/reviews/{content_id}/history", dependencies=[Depends(require_operator)])
def review_history(content_id: str, record_id: int | None = None, db: Session = Depends(get_db)):
    record = find_content(db, content_id, record_id)
    events = db.query(ReviewEvent).filter(ReviewEvent.content_record_id == record.id).order_by(ReviewEvent.version.desc()).limit(100).all()
    return [{"id": e.id, "version": e.version, "analysis_version": e.analysis_version, "actor": e.actor,
             "previous_status": e.previous_status, "previous_action": e.previous_action,
             "previous_comment": e.previous_comment, "action": e.action,
             "status": e.status, "comment": e.comment, "created_at": e.created_at} for e in events]
