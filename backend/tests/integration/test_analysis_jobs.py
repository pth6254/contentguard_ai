from models import AnalysisJob, Content
from services.analysis_job_service import process_one


def test_durable_job_masks_input_and_preserves_pii_rule(client, db_session, mock_predict):
    response = client.post("/api/jobs/analyze", json={"content_id": "async-one", "text": "연락처 010-1234-5678 로 연락하세요"})
    assert response.status_code == 202
    job_id = response.json()["id"]
    job = db_session.get(AnalysisJob, job_id)
    assert "010-1234-5678" not in job.text
    assert "전화번호" in job.pii_types
    assert client.post("/api/jobs/analyze", json={"content_id": "async-one", "text": "연락처 010-1234-5678 로 연락하세요"}).json()["id"] == job_id
    assert process_one(db_session)
    result = client.get(f"/api/jobs/{job_id}").json()
    assert result["status"] == "COMPLETED"
    record = db_session.get(Content, result["content_record_id"])
    assert record.risk_level in ("HIGH", "CRITICAL")
    assert any(rule["rule_id"] == "PII_DETECTED" for rule in record.triggered_rules)


def test_cancel_and_retry_failed_job(client, db_session, mock_predict, monkeypatch):
    first = client.post("/api/jobs/analyze", json={"content_id": "cancel-one", "text": "안전한 문장"}).json()["id"]
    assert client.post(f"/api/jobs/{first}/cancel").json()["status"] == "CANCELLED"
    assert not process_one(db_session)

    second = client.post("/api/jobs/analyze", json={"content_id": "retry-one", "text": "다시 처리할 문장"}).json()["id"]
    import services.analysis_job_service as service
    original = service.analyze_text
    def broken(*args, **kwargs):
        raise RuntimeError("internal-secret-must-not-leak")
    monkeypatch.setattr(service, "analyze_text", broken)
    for _ in range(3):
        job = db_session.get(AnalysisJob, second)
        from datetime import datetime
        job.next_attempt_at = datetime.utcnow()
        db_session.commit()
        assert process_one(db_session)
    assert client.get(f"/api/jobs/{second}").json()["last_error"] == "RuntimeError"
    monkeypatch.setattr(service, "analyze_text", original)
    assert client.post(f"/api/jobs/{second}/retry").json()["status"] == "PENDING"
    assert process_one(db_session)
    assert client.get(f"/api/jobs/{second}").json()["status"] == "COMPLETED"


def test_reanalysis_retains_review_and_requests_new_review(client, db_session, analyzed_content, mock_predict):
    record_id = analyzed_content["id"]
    assert client.post("/api/reviews/TEST001", json={"action": "approve"}).status_code == 200
    job = client.post(f"/api/contents/TEST001/reanalyze?record_id={record_id}")
    assert job.status_code == 202
    assert process_one(db_session)
    record = db_session.get(Content, record_id)
    assert record.review_status == "APPROVED"
    assert record.needs_re_review is True
    assert len(client.get(f"/api/contents/TEST001/analyses?record_id={record_id}").json()) == 2
    assert any(item["id"] == record_id for item in client.get("/api/contents?status=PENDING").json())
    assert client.post(f"/api/reviews/TEST001?record_id={record_id}", json={"action": "hold", "expected_version": 1, "expected_analysis_version": 2}).status_code == 200
    assert db_session.get(Content, record_id).needs_re_review is False
