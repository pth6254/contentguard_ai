"""Lease-based analysis worker. Persist only masked input and safe error types."""
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models import AnalysisJob, Content
from services.analysis_service import analyze_text
from services.content_service import add_analysis_run, save_analysis
from services.policy_service import load_policy

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
LEASE_SECONDS = 180


def process_one(db: Session) -> bool:
    now = datetime.utcnow()
    job = (db.query(AnalysisJob)
           .filter(AnalysisJob.status.in_(["PENDING", "PROCESSING"]),
                   AnalysisJob.next_attempt_at <= now)
           .order_by(AnalysisJob.next_attempt_at, AnalysisJob.id)
           .with_for_update(skip_locked=True).first())
    if not job:
        db.rollback()
        return False
    if job.cancel_requested:
        job.status, job.finished_at = "CANCELLED", now
        db.commit()
        return True
    if job.attempts >= MAX_ATTEMPTS:
        job.status, job.last_error, job.finished_at = "FAILED", "Worker lease expired", now
        db.commit()
        return True
    job.status = "PROCESSING"
    job.attempts += 1
    job.next_attempt_at = now + timedelta(seconds=LEASE_SECONDS)
    job_id = job.id
    db.commit()
    try:
        if job.kind == "new":
            existing = (db.query(Content).filter(Content.client_id == job.client_id,
                        Content.content_id == job.content_id).first())
            if existing:
                if existing.text != job.text:
                    raise ValueError("Content ID already belongs to different text")
                record_id = existing.id
            else:
                analysis = analyze_text(job.text, detected_pii=job.pii_types or [],
                                        policy=load_policy(db, job.client_id))
                db.expire_all()
                job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).with_for_update().one()
                if job.cancel_requested:
                    job.status, job.finished_at = "CANCELLED", datetime.utcnow()
                    db.commit()
                    return True
                record = save_analysis(db, content_id=job.content_id, client_id=job.client_id,
                                       source="job", **analysis)
                record_id = record.id
        elif job.kind == "reanalysis":
            analysis = analyze_text(job.text, detected_pii=job.pii_types or [],
                                    policy=load_policy(db, job.client_id))
            db.expire_all()
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).with_for_update().one()
            if job.cancel_requested:
                job.status, job.finished_at = "CANCELLED", datetime.utcnow()
                db.commit()
                return True
            record = db.query(Content).filter(Content.id == job.content_record_id).with_for_update().first()
            if not record:
                raise ValueError("Content no longer exists")
            record.risk_score = analysis["final"]["risk_score"]
            record.risk_level = analysis["final"]["risk_level"]
            record.recommended_action = analysis["final"]["recommended_action"]
            record.explanation = analysis["explanation"]
            record.explanation_json = analysis["explanation_json"]
            record.category_scores = analysis["category_scores"]
            record.triggered_rules = analysis["triggered_rules"]
            record.evidence_spans = analysis["evidence_spans"]
            record.calibrated_score = analysis["calibrated_score"]
            record.needs_re_review = record.review_status != "PENDING"
            add_analysis_run(db, record, analysis, "reanalysis")
            record_id = record.id
        else:
            raise ValueError("Unknown job kind")
        job = db.get(AnalysisJob, job_id)
        job.content_record_id = record_id
        job.status, job.finished_at, job.last_error = "COMPLETED", datetime.utcnow(), None
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(AnalysisJob, job_id)
        if not job:
            return True
        job.last_error = type(exc).__name__
        job.status = "FAILED" if job.attempts >= MAX_ATTEMPTS else "PENDING"
        job.next_attempt_at = datetime.utcnow() + timedelta(seconds=min(60, 5 * 2 ** job.attempts))
        if job.status == "FAILED":
            job.finished_at = datetime.utcnow()
        db.commit()
        logger.error("Analysis job %s failed: %s", job_id, type(exc).__name__)
    return True
