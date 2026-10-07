"""Worker liveness and actionable queue alerts for operators."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from auth import require_operator
from database import get_db
from models import AnalysisJob, WorkerHeartbeat, WebhookDelivery

router = APIRouter(prefix="/api/operations", tags=["operations"], dependencies=[Depends(require_operator)])


def worker_status(db):
    cutoff = datetime.utcnow() - timedelta(seconds=60)
    live = {kind for kind, in db.query(WorkerHeartbeat.kind).filter(WorkerHeartbeat.last_seen_at >= cutoff).distinct()}
    return {kind: "ok" if kind in live else "offline" for kind in ("analysis", "webhook")}


@router.get("")
def operations(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    workers = worker_status(db)
    counts = dict(db.query(AnalysisJob.status, func.count()).group_by(AnalysisJob.status).all())
    overdue = db.query(AnalysisJob).filter(AnalysisJob.status == "PENDING",
                AnalysisJob.created_at < now - timedelta(minutes=5)).count()
    expired = db.query(AnalysisJob).filter(AnalysisJob.status == "PROCESSING", AnalysisJob.next_attempt_at < now).count()
    failures = db.query(WebhookDelivery).filter(WebhookDelivery.status == "FAILED").count()
    recent = dict(db.query(AnalysisJob.status, func.count()).filter(AnalysisJob.finished_at >= now - timedelta(days=1))
                  .group_by(AnalysisJob.status).all())
    completed = sum(recent.get(status, 0) for status in ("COMPLETED", "DEGRADED", "FAILED"))
    alerts = [f"{kind} 워커가 응답하지 않습니다." for kind, status in workers.items() if status != "ok"]
    if overdue:
        alerts.append(f"5분 이상 대기한 작업 {overdue}건")
    if expired:
        alerts.append(f"실행 점유 시간이 만료된 작업 {expired}건")
    if counts.get("FAILED", 0) or counts.get("DEGRADED", 0):
        alerts.append(f"재시도 확인 필요: 실패 {counts.get('FAILED', 0)}건 · 임시 분석 {counts.get('DEGRADED', 0)}건")
    if failures:
        alerts.append(f"웹훅 발송 실패 {failures}건")
    return {"workers": workers, "jobs": counts, "overdue": overdue, "expired_leases": expired,
            "webhook_failures": failures, "alerts": alerts,
            "failure_rate_24h": (recent.get("FAILED", 0) + recent.get("DEGRADED", 0)) / completed if completed else None}
