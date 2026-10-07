from io import BytesIO

from unittest.mock import patch
from tests.conftest import MOCK_CLASSIFY_RESULT
from models import AnalysisJob, Content
from services.analysis_job_service import process_one
from services.policy_service import apply_policy


def test_policy_version_preview_and_escalation(client, db_session):
    initial = client.get("/api/policies/1")
    assert initial.status_code == 200 and initial.json()["version"] == 0
    draft = {"expected_version": 0, "category_min_levels": {"spam": "HIGH"},
             "review_categories": ["privacy"], "trigger_score": 60}
    assert client.post("/api/policies/1/preview", json=draft).status_code == 200
    saved = client.put("/api/policies/1", json=draft)
    assert saved.status_code == 200 and saved.json()["version"] == 1
    assert client.put("/api/policies/1", json=draft).status_code == 409
    assert client.put("/api/policies/1", json={**draft, "expected_version": 1,
              "category_min_levels": {"unknown": "HIGH"}}).status_code == 422
    score, level, action, review, note = apply_policy(.1, "LOW", {"spam": 80, "privacy": 65}, saved.json())
    assert (score, level, action, review) == (.6, "HIGH", "REVIEW", True)
    assert "v1" in note
    assert apply_policy(.9, "CRITICAL", {"spam": 80}, saved.json())[1] == "CRITICAL"
    model_result = {**MOCK_CLASSIFY_RESULT, "risk_level": "LOW", "risk_score": .1,
                    "category_scores": {**MOCK_CLASSIFY_RESULT["category_scores"], "spam": 80}}
    with patch("services.analysis_service.classify_and_explain", return_value=model_result):
        analyzed = client.post("/api/analyze", json={"content_id": "policy-one", "text": "광고성 게시물"})
    assert analyzed.status_code == 201
    assert analyzed.json()["risk_level"] == "HIGH"
    assert analyzed.json()["explanation_json"]["analysis_metadata"]["policy_version"] == "client-v1"
    future = {**draft, "expected_version": 1, "category_min_levels": {"spam": "CRITICAL"}}
    preview = client.post("/api/policies/1/preview", json=future).json()
    assert preview["changed"] == 1 and preview["changes"][0]["after"] == "CRITICAL"


def test_customer_portal_is_tenant_scoped(unauth_client, mock_predict, db_session):
    credentials = {"password": "test-password-123"}
    tokens = []
    for name in ("portal-first", "portal-second"):
        response = unauth_client.post("/auth/signup", json={"name": name, "email": f"{name}@example.com", **credentials})
        assert response.status_code == 201
        tokens.append(response.json()["access_token"])
    headers = [{"Authorization": "Bearer " + token} for token in tokens]
    created = unauth_client.post("/api/analyze", headers=headers[0], json={"content_id": "private-one", "text": "테스트 문장"})
    assert created.status_code == 201
    own = unauth_client.get("/auth/contents", headers=headers[0])
    other = unauth_client.get("/auth/contents", headers=headers[1])
    assert own.status_code == other.status_code == 200
    assert len(own.json()) == 1 and other.json() == []
    assert unauth_client.get("/auth/dashboard", headers=headers[1]).json()["total"] == 0
    assert unauth_client.get("/auth/webhooks", headers=headers[1]).json() == []
    assert unauth_client.get("/api/contents", headers=headers[1]).status_code == 401
    queued = unauth_client.post("/api/jobs/analyze", headers=headers[0], json={
        "content_id": "private-job", "text": "고객별로 구분해야 하는 문장"})
    assert queued.status_code == 202
    assert unauth_client.get(f"/api/jobs/{queued.json()['id']}", headers=headers[1]).status_code == 404
    record_id = created.json()["id"]
    assert unauth_client.get(f"/auth/contents/{record_id}", headers=headers[1]).status_code == 404
    assert unauth_client.post(f"/auth/contents/{record_id}/retry", headers=headers[1]).status_code == 404
    record = db_session.get(Content, record_id)
    record.explanation_json = {**record.explanation_json, "analysis_status": "fallback"}
    db_session.commit()
    assert unauth_client.post(f"/auth/contents/{record_id}/retry", headers=headers[0]).status_code == 202
    batch = unauth_client.post("/api/batches", headers=headers[0], files={"file": ("errors.csv", b"id,text\na,\n")},
                               data={"content_id_column": "id", "text_column": "text"})
    assert batch.status_code == 202
    assert unauth_client.get(f"/api/batches/{batch.json()['id']}/errors.csv", headers=headers[1]).status_code == 404
    denied = unauth_client.post("/api/jobs/retry", headers=headers[1], json={"job_ids": [queued.json()["id"]]}).json()
    assert denied["accepted"] == [] and len(denied["errors"]) == 1


def test_csv_batch_preview_queue_progress_and_masking(client, db_session, mock_predict):
    payload = "content_id,text\nrow-a,연락처 010-1234-5678\nrow-b,평범한 문장\nrow-a,중복 문장\n".encode("utf-8")
    files = {"file": ("items.csv", payload, "text/csv")}
    preview = client.post("/api/batches/preview", files=files)
    assert preview.status_code == 200 and preview.json()["rows"] == 3
    assert "010-1234-5678" not in str(preview.json()["sample"])
    submitted = client.post("/api/batches", files=files,
                            data={"content_id_column": "content_id", "text_column": "text"})
    assert submitted.status_code == 202, submitted.json()
    assert submitted.json()["accepted"] == 2 and submitted.json()["skipped"] == 1
    assert "010-1234-5678" not in db_session.query(AnalysisJob).filter(AnalysisJob.content_id == "row-a").one().text
    batch = client.get(f"/api/batches/{submitted.json()['id']}").json()
    assert batch["by_status"] == {"PENDING": 2}
    assert process_one(db_session) and process_one(db_session)
    batch = client.get(f"/api/batches/{submitted.json()['id']}").json()
    assert batch["by_status"] == {"COMPLETED": 2}
    assert db_session.query(Content).filter(Content.content_id.in_(["row-a", "row-b"])).count() == 2


def test_xlsx_preview_and_malformed_file(client):
    from openpyxl import Workbook
    book = Workbook()
    book.active.append(["content_id", "text"])
    book.active.append(["row-x", "정상적인 문장"])
    stream = BytesIO()
    book.save(stream)
    result = client.post("/api/batches/preview", files={"file": ("items.xlsx", stream.getvalue())})
    assert result.status_code == 200 and result.json()["columns"] == ["content_id", "text"]
    assert client.post("/api/batches/preview", files={"file": ("bad.xlsx", b"garbage")}).status_code == 422
