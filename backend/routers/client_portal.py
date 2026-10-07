"""Customer-only view of their own content, jobs, and webhook outcomes."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_client
from database import get_db
from models import AnalysisJob, Client, ClientPolicy, Content, ReviewEvent, WebhookDelivery
from schemas import ContentResponse

router = APIRouter(prefix="/auth", tags=["client-portal"])


@router.get("/dashboard")
def client_dashboard(client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    query = db.query(Content).filter(Content.client_id == client.id)
    counts = dict(db.query(Content.review_status, func.count(Content.id))
                  .filter(Content.client_id == client.id).group_by(Content.review_status).all())
    policy = db.query(ClientPolicy).filter(ClientPolicy.client_id == client.id).first()
    jobs = (db.query(AnalysisJob.status, func.count(AnalysisJob.id))
            .filter(AnalysisJob.client_id == client.id).group_by(AnalysisJob.status).all())
    deliveries = (db.query(WebhookDelivery.status, func.count(WebhookDelivery.id))
                  .join(ReviewEvent, ReviewEvent.id == WebhookDelivery.review_event_id)
                  .filter(ReviewEvent.client_id == client.id)
                  .group_by(WebhookDelivery.status).all())
    return {"client": {"id": client.id, "name": client.name}, "total": query.count(),
            "re_review_required": query.filter(Content.needs_re_review == True).count(),
            "by_status": counts, "jobs": dict(jobs), "webhooks": dict(deliveries),
            "policy_version": policy.version if policy else 0}


@router.get("/contents", response_model=list[ContentResponse])
def client_contents(response: Response, limit: int = Query(20, ge=1, le=100),
                    offset: int = Query(0, ge=0), search: str = Query("", max_length=200),
                    client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    query = db.query(Content).filter(Content.client_id == client.id)
    if search:
        query = query.filter(Content.content_id.ilike(f"%{search}%"))
    response.headers["X-Total-Count"] = str(query.count())
    return query.order_by(Content.created_at.desc(), Content.id.desc()).offset(offset).limit(limit).all()


@router.get("/contents/{record_id}", response_model=ContentResponse)
def client_content(record_id: int, client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    record = db.query(Content).filter(Content.id == record_id, Content.client_id == client.id).first()
    if not record:
        raise HTTPException(status_code=404, detail="콘텐츠가 없습니다.")
    return record


@router.post("/contents/{record_id}/retry", status_code=202)
def retry_content(record_id: int, client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    from routers.jobs import _enqueue_record, _result
    record = db.query(Content).filter(Content.id == record_id, Content.client_id == client.id).with_for_update().first()
    if not record:
        raise HTTPException(status_code=404, detail="콘텐츠가 없습니다.")
    active = db.query(AnalysisJob).filter(AnalysisJob.content_record_id == record.id,
                                       AnalysisJob.status.in_(["PENDING", "PROCESSING"])).first()
    if active:
        return _result(active)
    if (record.explanation_json or {}).get("analysis_status") != "fallback":
        raise HTTPException(status_code=409, detail="임시 분석 결과만 다시 분석할 수 있습니다.")
    return _enqueue_record(db, record)


@router.get("/webhooks")
def client_webhooks(client: Client = Depends(get_current_client), db: Session = Depends(get_db)):
    rows = (db.query(WebhookDelivery, ReviewEvent)
            .join(ReviewEvent, ReviewEvent.id == WebhookDelivery.review_event_id)
            .filter(ReviewEvent.client_id == client.id)
            .order_by(ReviewEvent.created_at.desc()).limit(50).all())
    return [{"event_id": delivery.id, "content_id": event.content_id,
             "review_version": event.version, "status": delivery.status,
             "attempts": delivery.attempts, "delivered_at": delivery.delivered_at}
            for delivery, event in rows]
