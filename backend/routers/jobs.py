"""Submit, inspect, retry, and cancel durable analysis work."""
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
            "content_record_id": job.content_record_id, "status": job.status,
            "attempts": job.attempts, "last_error": job.last_error,
            "created_at": job.created_at, "finished_at": job.finished_at}


def _owned_job(db: Session, job_id: str, client: Client | None) -> AnalysisJob:
    job = db.get(AnalysisJob, job_id)
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
    pii_types = []
    for rule in record.triggered_rules or []:
        if rule.get("rule_id") == "PII_DETECTED":
            pii_types.extend(part.strip() for part in rule.get("matched_text", "").split(",") if part.strip())
    job = AnalysisJob(id=secrets.token_hex(16), client_id=record.client_id,
                      content_id=record.content_id, content_record_id=record.id,
                      text=record.text, pii_types=sorted(set(pii_types)), kind="reanalysis",
                      status="PENDING", attempts=0, next_attempt_at=datetime.utcnow())
    db.add(job)
    db.commit()
    return _result(job)


@router.get("/jobs")
def list_jobs(limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db),
              client: Client | None = Depends(get_client_or_operator)):
    query = db.query(AnalysisJob)
    if client:
        query = query.filter(AnalysisJob.client_id == client.id)
    return [_result(job) for job in query.order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc()).limit(limit).all()]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db),
            client: Client | None = Depends(get_client_or_operator)):
    return _result(_owned_job(db, job_id, client))


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, db: Session = Depends(get_db),
              client: Client | None = Depends(get_client_or_operator)):
    job = _owned_job(db, job_id, client)
    if job.status != "FAILED":
        raise HTTPException(status_code=409, detail="실패한 작업만 재시도할 수 있습니다.")
    job.status, job.attempts, job.last_error = "PENDING", 0, None
    job.cancel_requested = False
    job.next_attempt_at = datetime.utcnow()
    job.finished_at = None
    db.commit()
    return _result(job)


@router.post("/jobs/{job_id}/cancel", status_code=202)
def cancel_job(job_id: str, db: Session = Depends(get_db),
               client: Client | None = Depends(get_client_or_operator)):
    job = _owned_job(db, job_id, client)
    if job.status not in ("PENDING", "PROCESSING"):
        raise HTTPException(status_code=409, detail="대기 중이거나 처리 중인 작업만 취소할 수 있습니다.")
    if job.status == "PENDING":
        job.status, job.finished_at = "CANCELLED", datetime.utcnow()
    else:
        job.cancel_requested = True
    db.commit()
    return _result(job)
