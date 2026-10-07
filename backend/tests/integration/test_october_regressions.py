from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import patch
import zipfile

from sqlalchemy.orm import sessionmaker

from models import AnalysisJob, AnalysisRun, Content, WorkerHeartbeat
from services import analysis_job_service as worker
from services.analysis_service import analyze_text
from tests.conftest import MOCK_CLASSIFY_RESULT


def result(score=.1, level="LOW", status="completed"):
    with patch("services.analysis_service.classify_and_explain", return_value={
            **MOCK_CLASSIFY_RESULT, "risk_score": score, "risk_level": level, "analysis_status": status}):
        return analyze_text("테스트 콘텐츠입니다")


def test_stale_review_rejected_after_reanalysis(client, db_session, analyzed_content):
    item = analyzed_content
    review_url = f"/api/reviews/TEST001?record_id={item['id']}"
    old_body = {"action": "approve", "expected_version": 0, "expected_analysis_version": item["analysis_version"]}
    client.post(f"/api/contents/TEST001/reanalyze?record_id={item['id']}")
    with patch.object(worker, "analyze_text", return_value=result()):
        assert worker.process_one(db_session)
    assert client.post(review_url, json=old_body).status_code == 409
    assert client.post(review_url, json={"action": "approve", "expected_version": 0}).status_code == 409
    latest = client.get(f"/api/contents/TEST001?record_id={item['id']}").json()
    assert client.post(review_url, json={**old_body, "expected_analysis_version": latest["analysis_version"]}).status_code == 200
    assert client.get(f"/api/reviews/TEST001/history?record_id={item['id']}").json()[0]["analysis_version"] == 2


def test_expired_worker_cannot_replace_newer_result(client, db_session, analyzed_content):
    record_id = analyzed_content["id"]
    job_id = client.post(f"/api/contents/TEST001/reanalyze?record_id={record_id}").json()["id"]
    low, high = result(), result(.9, "CRITICAL")
    Sessions = sessionmaker(bind=db_session.get_bind())
    def slow(*args, **kwargs):
        with Sessions() as second:
            job = second.get(AnalysisJob, job_id)
            job.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
            second.commit()
            with patch.object(worker, "analyze_text", return_value=high):
                worker.process_one(second)
        return low
    with patch.object(worker, "analyze_text", side_effect=slow):
        worker.process_one(db_session)
    db_session.expire_all()
    assert db_session.get(Content, record_id).risk_level == "CRITICAL"
    assert db_session.get(Content, record_id).analysis_version == 2
    assert db_session.query(AnalysisRun).filter_by(content_record_id=record_id).count() == 2
    assert db_session.get(AnalysisJob, job_id).status == "COMPLETED"


def test_lease_renewal_respects_owner(client, db_session):
    job_id = client.post("/api/jobs/analyze", json={"content_id": "renew", "text": "내용"}).json()["id"]
    job = db_session.get(AnalysisJob, job_id)
    job.status, job.lease_token = "PROCESSING", "new-owner"
    past = datetime.utcnow() - timedelta(seconds=10)
    job.next_attempt_at = past
    db_session.commit()
    Sessions = sessionmaker(bind=db_session.get_bind())
    worker.renew_lease(Sessions, job_id, "old-owner")
    db_session.expire_all()
    assert db_session.get(AnalysisJob, job_id).next_attempt_at == past
    worker.renew_lease(Sessions, job_id, "new-owner")
    db_session.expire_all()
    assert db_session.get(AnalysisJob, job_id).next_attempt_at > datetime.utcnow()


def test_fallback_retries_then_degrades_and_can_recover(client, db_session):
    job_id = client.post("/api/jobs/analyze", json={"content_id": "fallback", "text": "내용"}).json()["id"]
    with patch.object(worker, "analyze_text", return_value=result(status="fallback")):
        for _ in range(3):
            db_session.get(AnalysisJob, job_id).next_attempt_at = datetime.utcnow()
            db_session.commit()
            worker.process_one(db_session)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "DEGRADED"
    assert client.post(f"/api/jobs/{job_id}/retry").status_code == 202
    with patch.object(worker, "analyze_text", return_value=result()):
        worker.process_one(db_session)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "COMPLETED"
    assert db_session.query(Content).filter_by(content_id="fallback").count() == 1


def test_content_and_job_result_commit_atomically(client, db_session):
    job_id = client.post("/api/jobs/analyze", json={"content_id": "atomic", "text": "내용"}).json()["id"]
    original = worker.save_analysis
    def fail_after_save(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("simulated completion failure")
    with patch.object(worker, "analyze_text", return_value=result()), patch.object(worker, "save_analysis", side_effect=fail_after_save):
        worker.process_one(db_session)
    assert db_session.query(Content).filter_by(content_id="atomic").count() == 0
    assert db_session.query(AnalysisRun).count() == 0
    assert db_session.get(AnalysisJob, job_id).status == "PENDING"


def test_policy_preview_can_remove_customer_escalation_but_not_global_rules(client, db_session):
    policy = {"category_min_levels": {"spam": "CRITICAL"}, "expected_version": 0, "trigger_score": 60}
    assert client.put("/api/policies/1", json=policy).status_code == 200
    model = {**MOCK_CLASSIFY_RESULT, "risk_score": .1, "risk_level": "LOW",
             "category_scores": {**MOCK_CLASSIFY_RESULT["category_scores"], "spam": 80}}
    with patch("services.analysis_service.classify_and_explain", return_value=model):
        plain = client.post("/api/analyze", json={"content_id": "policy-low", "text": "일반 문장"}).json()
        private = client.post("/api/analyze", json={"content_id": "policy-pii", "text": "전화 010-1234-5678"}).json()
    preview = client.post("/api/policies/1/preview", json={"expected_version": 1}).json()
    changes = {item["record_id"]: item for item in preview["changes"]}
    assert changes[plain["id"]]["after"] == "LOW"
    assert changes[private["id"]]["after"] in ("HIGH", "CRITICAL")
    assert preview["skipped"] == 0


def test_frozen_evaluations_survive_label_and_analysis_changes(client, db_session, analyzed_content):
    record_id = analyzed_content["id"]
    label_url = f"/api/evaluations/labels/{record_id}"
    client.put(label_url, json={"expected_level": "CRITICAL"})
    dataset = client.post("/api/evaluations/datasets", json={"name": "fixed"}).json()
    path = f"/api/evaluations/datasets/{dataset['id']}/reports"
    first = client.post(path, json={"name": "before"}).json()
    assert first["metrics"]["accuracy"] == 1
    client.put(label_url, json={"expected_level": "LOW"})
    client.post(f"/api/contents/TEST001/reanalyze?record_id={record_id}")
    with patch.object(worker, "analyze_text", return_value=result()):
        worker.process_one(db_session)
    second = client.post(path, json={"name": "after"}).json()
    assert second["metrics"]["accuracy"] == 0
    assert client.get(path).json()[1]["metrics"] == first["metrics"]
    missing = client.post(path, json={"name": "missing model", "model": "not-present"}).json()
    assert missing["metrics"]["skipped"] == 1


def test_job_pagination_and_selected_retry(client, db_session):
    for index in range(105):
        db_session.add(AnalysisJob(id=f"page-{index}", client_id=1, content_id=f"page-{index}", text="내용", kind="new", status="FAILED"))
    db_session.commit()
    response = client.get("/api/jobs?limit=20&offset=100&status=FAILED&search=page-")
    assert len(response.json()) == 5 and response.headers["X-Total-Count"] == "105"
    retried = client.post("/api/jobs/retry", json={"job_ids": ["page-0", "missing"]}).json()
    assert retried["accepted"] == ["page-0"] and len(retried["errors"]) == 1


def test_batch_errors_keep_original_row_numbers(client):
    payload = "content_id,text\n\na,정상\na,중복\nb,\n".encode()
    response = client.post("/api/batches", files={"file": ("rows.csv", payload)},
                           data={"content_id_column": "content_id", "text_column": "text"})
    assert response.status_code == 202
    assert sorted(item["row"] for item in response.json()["errors"]) == [4, 5]
    errors = client.get(f"/api/batches/{response.json()['id']}/errors.csv")
    assert errors.status_code == 200 and "4," in errors.text and "5," in errors.text


def test_batch_rejects_expansion_before_workbook_parser(client, monkeypatch):
    import routers.batches as batches
    monkeypatch.setattr(batches, "MAX_UNCOMPRESSED_BYTES", 1024)
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("sheet.xml", "a" * 2048)
    with patch("openpyxl.load_workbook", side_effect=AssertionError("must reject before parsing")):
        assert client.post("/api/batches/preview", files={"file": ("limit.xlsx", stream.getvalue())}).status_code == 413


def test_batch_stops_after_row_limit(client, monkeypatch):
    import routers.batches as batches
    consumed = []
    def rows(*args, **kwargs):
        yield ["id", "text"]
        for index in range(1000):
            consumed.append(index)
            yield [str(index), "body"]
    monkeypatch.setattr(batches.csv, "reader", rows)
    assert client.post("/api/batches/preview", files={"file": ("limit.csv", b"test")}).status_code == 413
    assert len(consumed) == 501


def test_operations_detects_stale_worker_and_waiting_job(client, db_session):
    db_session.add(WorkerHeartbeat(id="a", kind="analysis", last_seen_at=datetime.utcnow()))
    db_session.add(WorkerHeartbeat(id="b", kind="webhook", last_seen_at=datetime.utcnow() - timedelta(minutes=2)))
    db_session.add(AnalysisJob(id="waiting", content_id="waiting", text="내용", kind="new", status="PENDING",
                               created_at=datetime.utcnow() - timedelta(minutes=10)))
    db_session.commit()
    state = client.get("/api/operations").json()
    assert state["workers"] == {"analysis": "ok", "webhook": "offline"}
    assert state["overdue"] == 1 and len(state["alerts"]) == 2
