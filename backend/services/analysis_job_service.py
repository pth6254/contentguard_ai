"""Durable analysis with renewable leases and fenced, atomic result writes."""
import logging
import secrets
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, sessionmaker

from models import AnalysisJob, Content
from services.analysis_service import analyze_text
from services.content_service import add_analysis_run, save_analysis
from services.policy_service import load_policy
from services.worker_health import periodic

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
LEASE_SECONDS = 180


def renew_lease(session_factory, job_id: str, token: str) -> None:
    with session_factory() as db:
        db.query(AnalysisJob).filter(AnalysisJob.id == job_id, AnalysisJob.lease_token == token,
                                    AnalysisJob.status == "PROCESSING").update({
            AnalysisJob.next_attempt_at: datetime.utcnow() + timedelta(seconds=LEASE_SECONDS)
        }, synchronize_session=False)
        db.commit()


def _owned(db, job_id, token):
    db.expire_all()
    return (db.query(AnalysisJob).filter(AnalysisJob.id == job_id, AnalysisJob.lease_token == token,
            AnalysisJob.status == "PROCESSING").with_for_update().populate_existing().first())


def _replace_analysis(db, record, analysis):
    record.risk_score = analysis["final"]["risk_score"]
    record.risk_level = analysis["final"]["risk_level"]
    record.recommended_action = analysis["final"]["recommended_action"]
    for key in ("text", "explanation", "explanation_json", "category_scores", "triggered_rules",
                "evidence_spans", "calibrated_score"):
        setattr(record, key, analysis[key])
    record.needs_re_review = record.review_status != "PENDING"
    add_analysis_run(db, record, analysis, "reanalysis")


def process_one(db: Session) -> bool:
    now = datetime.utcnow()
    job = (db.query(AnalysisJob)
           .filter(AnalysisJob.status.in_(["PENDING", "PROCESSING"]), AnalysisJob.next_attempt_at <= now)
           .order_by(AnalysisJob.next_attempt_at, AnalysisJob.id).with_for_update(skip_locked=True).first())
    if not job:
        db.rollback()
        return False
    if job.cancel_requested or job.attempts >= MAX_ATTEMPTS:
        job.status = "CANCELLED" if job.cancel_requested else "FAILED"
        job.last_error = None if job.cancel_requested else "WorkerLeaseExpired"
        job.finished_at, job.lease_token = now, None
        db.commit()
        return True
    token = secrets.token_hex(16)
    job.status, job.lease_token = "PROCESSING", token
    job.attempts += 1
    job.next_attempt_at = now + timedelta(seconds=LEASE_SECONDS)
    job_id = job.id
    text, pii_types, client_id = job.text, job.pii_types or [], job.client_id
    db.commit()
    factory = sessionmaker(bind=db.get_bind())
    try:
        policy = load_policy(db, client_id)
        # Release the DB connection while waiting for a model response.
        db.commit()
        with periodic(lambda: renew_lease(factory, job_id, token), interval=30):
            analysis = analyze_text(text, detected_pii=pii_types, policy=policy)
        job = _owned(db, job_id, token)
        if not job:
            db.rollback()
            return True
        if job.cancel_requested:
            job.status, job.finished_at, job.lease_token = "CANCELLED", datetime.utcnow(), None
            db.commit()
            return True
        record = None
        if job.content_record_id:
            record = db.query(Content).filter(Content.id == job.content_record_id).with_for_update().first()
            if not record:
                raise ValueError("Content no longer exists")
        elif job.kind == "new":
            existing = db.query(Content).filter(Content.client_id == job.client_id,
                          Content.content_id == job.content_id).first()
            if existing:
                raise ValueError("Content ID was already analyzed by another request")
        else:
            raise ValueError("Unknown job kind")
        if record:
            _replace_analysis(db, record, analysis)
        else:
            record = save_analysis(db, content_id=job.content_id, client_id=job.client_id,
                                   source="job", commit=False, **analysis)
        job.content_record_id = record.id
        fallback = analysis["explanation_json"].get("analysis_status") != "completed"
        job.status = ("PENDING" if job.attempts < MAX_ATTEMPTS else "DEGRADED") if fallback else "COMPLETED"
        job.last_error = "LLMUnavailable" if fallback else None
        job.finished_at = None if job.status == "PENDING" else datetime.utcnow()
        job.next_attempt_at = datetime.utcnow() + timedelta(seconds=min(60, 5 * 2 ** job.attempts))
        job.lease_token = None
        # Content, history and completion are a single transaction.
        db.commit()
    except Exception as exc:
        db.rollback()
        job = _owned(db, job_id, token)
        if not job:
            db.rollback()
            return True
        job.last_error = type(exc).__name__
        job.status = "CANCELLED" if job.cancel_requested else ("FAILED" if job.attempts >= MAX_ATTEMPTS else "PENDING")
        job.next_attempt_at = datetime.utcnow() + timedelta(seconds=min(60, 5 * 2 ** job.attempts))
        job.finished_at = datetime.utcnow() if job.status in ("FAILED", "CANCELLED") else None
        job.lease_token = None
        db.commit()
        logger.error("Analysis job %s failed: %s", job_id, type(exc).__name__)
    return True