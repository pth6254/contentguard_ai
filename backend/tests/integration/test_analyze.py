from models import Content
from tests.conftest import MOCK_FINAL_RESULT


class TestAnalyzeAuth:
    def test_missing_api_key_returns_401(self, unauth_client, mock_predict):
        response = unauth_client.post(
            "/api/analyze",
            json={"content_id": "AUTH001", "text": "테스트"},
        )
        assert response.status_code == 401

    def test_invalid_api_key_returns_401(self, unauth_client, mock_predict):
        response = unauth_client.post(
            "/api/analyze",
            json={"content_id": "AUTH001", "text": "테스트"},
            headers={"Authorization": "Bearer invalid-key"},
        )
        assert response.status_code == 401


class TestAnalyzeEndpoint:
    def test_returns_201_on_success(self, client, mock_predict):
        response = client.post(
            "/api/analyze",
            json={"content_id": "C001", "text": "테스트 콘텐츠"},
        )
        assert response.status_code == 201

    def test_response_contains_correct_risk_fields(self, client, mock_predict):
        response = client.post(
            "/api/analyze",
            json={"content_id": "C001", "text": "테스트 콘텐츠"},
        )
        data = response.json()
        assert data["content_id"] == "C001"
        assert data["risk_score"] == MOCK_FINAL_RESULT["risk_score"]
        assert data["risk_level"] == MOCK_FINAL_RESULT["risk_level"]
        assert data["recommended_action"] == MOCK_FINAL_RESULT["recommended_action"]

    def test_new_content_status_is_pending(self, client, mock_predict):
        response = client.post(
            "/api/analyze",
            json={"content_id": "C001", "text": "테스트"},
        )
        assert response.json()["review_status"] == "PENDING"

    def test_explanation_is_stored(self, client, mock_predict):
        response = client.post(
            "/api/analyze",
            json={"content_id": "C001", "text": "테스트"},
        )
        # explanation은 explanation_json["summary"]로 설정됨
        assert response.json()["explanation"] == "테스트 설명입니다."

    def test_v2_fields_present_in_response(self, client, mock_predict):
        response = client.post(
            "/api/analyze",
            json={"content_id": "C001", "text": "테스트"},
        )
        data = response.json()
        assert "category_scores" in data
        assert "triggered_rules" in data
        assert "evidence_spans" in data
        assert "explanation_json" in data
        assert "calibrated_score" in data
        assert "raw_model_score" in data

    def test_explanation_json_has_required_keys(self, client, mock_predict):
        response = client.post(
            "/api/analyze",
            json={"content_id": "C001", "text": "테스트"},
        )
        ej = response.json()["explanation_json"]
        assert ej is not None
        for key in ("summary", "score_explanation", "main_reasons", "evidence",
                    "recommended_operator_check", "confidence_note"):
            assert key in ej

    def test_duplicate_content_id_returns_400(self, client, mock_predict):
        client.post("/api/analyze", json={"content_id": "C001", "text": "첫 번째"})
        response = client.post("/api/analyze", json={"content_id": "C001", "text": "두 번째"})
        assert response.status_code == 400
        assert "C001" in response.json()["detail"]

    def test_empty_text_returns_422(self, client, mock_predict):
        response = client.post("/api/analyze", json={"content_id": "C001", "text": ""})
        assert response.status_code == 422

    def test_missing_content_id_returns_422(self, client, mock_predict):
        response = client.post("/api/analyze", json={"text": "텍스트"})
        assert response.status_code == 422


class TestContentStatusEndpoint:
    def test_returns_status_for_own_content(self, client, analyzed_content):
        response = client.get(f"/api/contents/{analyzed_content['content_id']}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["content_id"] == analyzed_content["content_id"]
        assert data["risk_level"] == analyzed_content["risk_level"]
        assert data["review_status"] == "PENDING"
        assert "text" not in data

    def test_returns_403_for_other_clients_content(self, client, db_session, mock_predict):
        other_content = Content(
            content_id="OTHER001",
            text="다른 클라이언트 콘텐츠",
            client_id=999,
            risk_score=0.5,
            risk_level="MEDIUM",
            recommended_action="REVIEW",
        )
        db_session.add(other_content)
        db_session.commit()

        response = client.get("/api/contents/OTHER001/status")
        assert response.status_code == 403

    def test_returns_404_for_nonexistent_content(self, client):
        response = client.get("/api/contents/NOTFOUND/status")
        assert response.status_code == 404

    def test_returns_401_without_api_key(self, unauth_client):
        response = unauth_client.get("/api/contents/ANY/status")
        assert response.status_code == 401
