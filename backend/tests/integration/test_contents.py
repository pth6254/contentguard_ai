from tests.conftest import MOCK_FINAL_RESULT, OPERATOR_SECRET


class TestContentsAuth:
    def test_missing_secret_returns_401(self, unauth_client):
        response = unauth_client.get("/api/contents")
        assert response.status_code == 401

    def test_wrong_secret_returns_401(self, unauth_client):
        response = unauth_client.get("/api/contents", headers={"x-admin-secret": "wrong"})
        assert response.status_code == 401

    def test_correct_secret_returns_200(self, unauth_client):
        response = unauth_client.get("/api/contents", headers={"x-admin-secret": OPERATOR_SECRET})
        assert response.status_code == 200


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


class TestGetContentsPagination:
    def test_x_total_count_header_present(self, analyzed_content, client):
        response = client.get("/api/contents")
        assert "x-total-count" in response.headers
        assert response.headers["x-total-count"] == "1"

    def test_x_total_count_zero_when_empty(self, client):
        response = client.get("/api/contents")
        assert response.headers["x-total-count"] == "0"

    def test_limit_restricts_results(self, analyzed_content, client):
        response = client.get("/api/contents?limit=1")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_offset_skips_results(self, analyzed_content, client):
        response = client.get("/api/contents?offset=1")
        assert response.status_code == 200
        assert response.json() == []

    def test_limit_minimum_is_one(self, client):
        response = client.get("/api/contents?limit=0")
        assert response.status_code == 422

    def test_limit_maximum_is_200(self, client):
        response = client.get("/api/contents?limit=201")
        assert response.status_code == 422

    def test_offset_cannot_be_negative(self, client):
        response = client.get("/api/contents?offset=-1")
        assert response.status_code == 422


class TestGetContentsSearch:
    def test_search_matches_text(self, analyzed_content, client):
        response = client.get("/api/contents?search=테스트")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_search_matches_content_id(self, analyzed_content, client):
        response = client.get("/api/contents?search=TEST001")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_search_is_case_insensitive(self, analyzed_content, client):
        response = client.get("/api/contents?search=test001")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_search_no_match_returns_empty(self, analyzed_content, client):
        response = client.get("/api/contents?search=존재하지않는텍스트xyz")
        assert response.status_code == 200
        assert response.json() == []

    def test_search_updates_x_total_count(self, analyzed_content, client):
        response = client.get("/api/contents?search=존재하지않는텍스트xyz")
        assert response.headers["x-total-count"] == "0"


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


class TestDeleteContent:
    def test_delete_returns_204(self, analyzed_content, client):
        response = client.delete("/api/contents/TEST001")
        assert response.status_code == 204

    def test_deleted_content_not_found(self, analyzed_content, client):
        client.delete("/api/contents/TEST001")
        response = client.get("/api/contents/TEST001")
        assert response.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        response = client.delete("/api/contents/NONEXISTENT")
        assert response.status_code == 404

    def test_delete_removes_from_list(self, analyzed_content, client):
        client.delete("/api/contents/TEST001")
        items = client.get("/api/contents").json()
        assert all(i["content_id"] != "TEST001" for i in items)

    def test_delete_requires_auth(self, unauth_client):
        response = unauth_client.delete("/api/contents/TEST001")
        assert response.status_code == 401


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
