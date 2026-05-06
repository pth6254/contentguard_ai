from tests.conftest import MOCK_FINAL_RESULT


class TestGetContents:
    def test_returns_empty_list_when_no_content(self, client):
        response = client.get("/api/contents")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_analyzed_item(self, analyzed_content, client):
        response = client.get("/api/contents")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["content_id"] == "TEST001"

    def test_filter_by_pending_status(self, analyzed_content, client):
        response = client.get("/api/contents?status=PENDING")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["review_status"] == "PENDING"

    def test_filter_by_status_excludes_non_matching(self, analyzed_content, client):
        response = client.get("/api/contents?status=APPROVED")
        assert response.status_code == 200
        assert response.json() == []

    def test_filter_by_risk_level(self, analyzed_content, client):
        level = MOCK_FINAL_RESULT["risk_level"]
        response = client.get(f"/api/contents?risk_level={level}")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_filter_by_risk_level_case_insensitive(self, analyzed_content, client):
        level = MOCK_FINAL_RESULT["risk_level"].lower()
        response = client.get(f"/api/contents?risk_level={level}")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_sort_by_risk_score_returns_200(self, analyzed_content, client):
        response = client.get("/api/contents?sort_by=risk_score")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_sort_by_created_at_returns_200(self, analyzed_content, client):
        response = client.get("/api/contents?sort_by=created_at")
        assert response.status_code == 200


class TestGetContentById:
    def test_returns_content(self, analyzed_content, client):
        response = client.get("/api/contents/TEST001")
        assert response.status_code == 200
        data = response.json()
        assert data["content_id"] == "TEST001"
        assert data["text"] == "테스트 콘텐츠입니다"

    def test_returns_404_for_unknown_id(self, client):
        response = client.get("/api/contents/NONEXISTENT")
        assert response.status_code == 404

    def test_404_detail_mentions_content_id(self, client):
        response = client.get("/api/contents/GHOST123")
        assert "GHOST123" in response.json()["detail"]


class TestGetPredictions:
    def test_returns_predictions_list(self, analyzed_content, client):
        response = client.get("/api/contents/TEST001/predictions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_predictions_have_required_fields(self, analyzed_content, client):
        preds = client.get("/api/contents/TEST001/predictions").json()
        for pred in preds:
            assert "model_name" in pred
            assert "risk_score" in pred
            assert "risk_level" in pred
            assert "is_selected" in pred
            assert "is_shadow" in pred

    def test_returns_404_for_unknown_content(self, client):
        response = client.get("/api/contents/NONEXISTENT/predictions")
        assert response.status_code == 404
