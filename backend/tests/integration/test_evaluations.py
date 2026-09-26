from models import AnalysisRun, Content


def test_label_is_explicit_and_independent_of_review(client, analyzed_content):
    record_id = analyzed_content["id"]
    assert client.get("/api/evaluations/summary").json()["labeled"] == 0
    assert client.post("/api/reviews/TEST001", json={"action": "approve"}).status_code == 200
    assert client.get("/api/evaluations/summary").json()["labeled"] == 0
    response = client.put(f"/api/evaluations/labels/{record_id}", json={
        "expected_level": "LOW", "category": "spam", "reason": "test@example.com 오탐"})
    assert response.status_code == 200
    assert "test@example.com" not in response.json()["reason"]
    summary = client.get("/api/evaluations/summary").json()
    assert summary["labeled"] == 1
    assert summary["false_positives"] == 1
    assert summary["accuracy"] == 0
    assert summary["by_category"]["spam"] == {"total": 1, "correct": 0}
    assert client.get("/api/active-learning/candidates").json()[0]["operator_level"] == "LOW"


def test_analysis_run_is_stored_and_removed_with_content(client, analyzed_content, db_session):
    record_id = analyzed_content["id"]
    runs = client.get(f"/api/contents/TEST001/analyses?record_id={record_id}")
    assert runs.status_code == 200
    assert len(runs.json()) == 1
    assert runs.json()[0]["status"] == "completed"
    assert runs.json()[0]["source"] == "api"
    assert runs.json()[0]["latency_ms"] is not None
    assert client.delete(f"/api/contents/TEST001?record_id={record_id}").status_code == 204
    assert db_session.query(AnalysisRun).count() == 0
    assert db_session.query(Content).count() == 0


def test_fallback_label_is_not_counted_as_model_accuracy(client, analyzed_content, db_session):
    record = db_session.get(Content, analyzed_content["id"])
    record.explanation_json = {**record.explanation_json, "analysis_status": "fallback"}
    db_session.commit()
    client.put(f"/api/evaluations/labels/{record.id}", json={"expected_level": "CRITICAL"})
    summary = client.get("/api/evaluations/summary").json()
    assert summary["labeled"] == 1
    assert summary["evaluated"] == 0
    assert summary["skipped"] == 1
    assert summary["accuracy"] is None
