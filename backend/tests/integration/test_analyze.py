from tests.conftest import MOCK_FINAL_RESULT, MOCK_PREDICTIONS


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
        assert response.json()["explanation"] == "테스트 설명입니다."

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

    def test_stores_one_prediction_per_model(self, client, mock_predict):
        client.post("/api/analyze", json={"content_id": "C001", "text": "테스트"})
        preds = client.get("/api/contents/C001/predictions").json()
        assert len(preds) == len(MOCK_PREDICTIONS)

    def test_selected_model_is_logistic_regression(self, client, mock_predict):
        client.post("/api/analyze", json={"content_id": "C001", "text": "테스트"})
        preds = client.get("/api/contents/C001/predictions").json()
        selected = [p for p in preds if p["is_selected"]]
        assert len(selected) == 1
        assert selected[0]["model_name"] == "logistic_regression"

    def test_shadow_models_are_marked(self, client, mock_predict):
        client.post("/api/analyze", json={"content_id": "C001", "text": "테스트"})
        preds = client.get("/api/contents/C001/predictions").json()
        shadow = [p for p in preds if p["is_shadow"]]
        assert len(shadow) == 2
