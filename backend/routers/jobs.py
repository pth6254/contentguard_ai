"""Submit, inspect, retry, and cancel durable analysis work."""
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_client_or_operator, require_operator
from database import get_db
from limiter import limiter
from models import AnalysisJob, Client, Content, Operator
from schemas import AnalyzeRequest
from services.content_lookup import find_content
from services.rule_detector import mask_pii

router = APIRouter(prefix="/api", tags=["analysis-jobs"])


def _result(job: AnalysisJob) -> dict:
    return {"id": job.id, "kind": job.kind, "content_id": job.content_id,
            "client_id": job.client_id, "batch_id": job.batch_id, "cancel_requested": job.cancel_requested,
            "content_record_id": job.content_record_id, "status": job.status,
            "attempts": job.attempts, "last_error": job.last_error,
            "created_at": job.created_at, "finished_at": job.finished_at}


def _owned_job(db: Session, job_id: str, client: Client | None, lock=False) -> AnalysisJob:
    query = db.query(AnalysisJob).filter(AnalysisJob.id == job_id)
    job = (query.with_for_update() if lock else query).populate_existing().first()
    if not job or (client and job.client_id != client.id):
        raise HTTPException(status_code=404, detail="분석 작업을 찾을 수 없습니다.")
    return job


@router.post("/jobs/analyze", status_code=202)
@limiter.limit("60/hour")
def submit_analysis(request: Request, body: AnalyzeRequest, db: Session = Depends(get_db),
                    client: Client | None = Depends(get_client_or_operator)):
    client_id = client.id if client else None
    existing = db.query(Content).filter(Content.client_id == client_id, Content.content_id == body.content_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="이미 분석된 콘텐츠 ID입니다.")
    masked, pii_types = mask_pii(body.text)
    key = f"client:{client_id if client_id is not None else 'operator'}:{body.content_id}"
    job = db.query(AnalysisJob).filter(AnalysisJob.submission_key == key).first()
    if job:
        if job.text != masked:
            raise HTTPException(status_code=409, detail="같은 콘텐츠 ID에 다른 텍스트가 접수되었습니다.")
        return _result(job)
    job = AnalysisJob(id=secrets.token_hex(16), client_id=client_id, submission_key=key,
                      content_id=body.content_id, text=masked, pii_types=pii_types,
                      kind="new", status="PENDING", attempts=0, next_attempt_at=datetime.utcnow())
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        job = db.query(AnalysisJob).filter(AnalysisJob.submission_key == key).first()
        if not job or job.text != masked:
            raise HTTPException(status_code=409, detail="같은 콘텐츠 ID가 처리 중입니다.")
    return _result(job)


@router.post("/contents/{content_id}/reanalyze", status_code=202)
def reanalyze(content_id: str, record_id: int = Query(...), db: Session = Depends(get_db),
              operator: Operator | None = Depends(require_operator)):
    record = find_content(db, content_id, record_id, lock=True)
    active = db.query(AnalysisJob).filter(AnalysisJob.content_record_id == record.id,
               AnalysisJob.status.in_(["PENDING", "PROCESSING"])).first()
    if active:
        return _result(active)
    return _enqueue_record(db, record)


def _enqueue_record(db, record):
    pii_types = []
    for rule in record.triggered_rules or []:
        if rule.get("rule_id") == "PII_DETECTED":
            pii_types.extend(part.strip() for part in rule.get("matched_text", "").split(",") if part.strip())
    masked, detected = mask_pii(record.text)
    job = AnalysisJob(id=secrets.token_hex(16), client_id=record.client_id,
                      content_id=record.content_id, content_record_id=record.id,
                      text=masked, pii_types=sorted(set(pii_types + detected)), kind="reanalysis",
                      status="PENDING", attempts=0, next_attempt_at=datetime.utcnow())
    db.add(job)
    db.commit()
    return _result(job)


@router.get("/jobs")
def list_jobs(response: Response, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
              status: str | None = Query(None, pattern="^(PENDING|PROCESSING|COMPLETED|FAILED|CANCELLED|DEGRADED)$"),
              search: str = Query("", max_length=200), batch_id: str | None = Query(None, max_length=32),
              client_id: int | None = Query(None, ge=1), db: Session = Depends(get_db),
              client: Client | None = Depends(get_client_or_operator)):
    query = db.query(AnalysisJob)
    if client:
        query = query.filter(AnalysisJob.client_id == client.id)
    elif client_id:
        query = query.filter(AnalysisJob.client_id == client_id)
    if status:
        query = query.filter(AnalysisJob.status == status)
    if search:
        query = query.filter(AnalysisJob.content_id.ilike(f"%{search}%"))
    if batch_id:
        query = query.filter(AnalysisJob.batch_id == batch_id)
    response.headers["X-Total-Count"] = str(query.count())
    return [_result(job) for job in query.order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc()).offset(offset).limit(limit).all()]


class RetryBatch(BaseModel):
    job_ids: list[str] = Field(..., min_length=1, max_length=100)


def _prepare_retry(db, job):
    record = (db.query(Content).filter(Content.id == job.content_record_id).with_for_update().first()
              if job.content_record_id else None)
    legacy_fallback = job.status == "COMPLETED" and record and (record.explanation_json or {}).get("analysis_status") == "fallback"
    if job.status not in ("FAILED", "DEGRADED") and not legacy_fallback:
        raise HTTPException(status_code=409, detail="실패 또는 임시 분석 작업만 재시도할 수 있습니다.")
    if record and db.query(AnalysisJob).filter(AnalysisJob.content_record_id == record.id,
            AnalysisJob.id != job.id, AnalysisJob.status.in_(["PENDING", "PROCESSING"])).first():
        raise HTTPException(status_code=409, detail="이 콘텐츠는 이미 분석 중입니다.")
    job.status, job.attempts, job.last_error = "PENDING", 0, None
    job.cancel_requested, job.lease_token = False, None
    job.next_attempt_at, job.finished_at = datetime.utcnow(), None


@router.post("/jobs/retry", status_code=202)
def retry_many(body: RetryBatch, db: Session = Depends(get_db),
               client: Client | None = Depends(get_client_or_operator)):
    accepted, errors = [], []
    for job_id in dict.fromkeys(body.job_ids):
        try:
            job = _owned_job(db, job_id, client, lock=True)
            _prepare_retry(db, job)
            db.commit()
            accepted.append(job_id)
        except HTTPException as exc:
            db.rollback()
            errors.append({"id": job_id, "reason": exc.detail})
    return {"accepted": accepted, "errors": errors}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db),
            client: Client | None = Depends(get_client_or_operator)):
    return _result(_owned_job(db, job_id, client))


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, db: Session = Depends(get_db),
              client: Client | None = Depends(get_client_or_operator)):
    job = _owned_job(db, job_id, client, lock=True)
    _prepare_retry(db, job)
    db.commit()
    return _result(job)


@router.post("/jobs/{job_id}/cancel", status_code=202)
def cancel_job(job_id: str, db: Session = Depends(get_db),
               client: Client | None = Depends(get_client_or_operator)):
    job = _owned_job(db, job_id, client, lock=True)
    if job.status not in ("PENDING", "PROCESSING"):
        raise HTTPException(status_code=409, detail="대기 중이거나 처리 중인 작업만 취소할 수 있습니다.")
    if job.status == "PENDING":
        job.status, job.finished_at = "CANCELLED", datetime.utcnow()
    else:
        job.cancel_requested = True
    db.commit()
    return _result(job)
