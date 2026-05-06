import pytest


class TestReviewEndpoint:
    @pytest.mark.parametrize("action,expected_status", [
        ("approve", "APPROVED"),
        ("remove", "REMOVED"),
        ("hold", "HELD"),
        ("monitor", "MONITORED"),
    ])
    def test_action_maps_to_correct_status(self, analyzed_content, client, action, expected_status):
        response = client.post(f"/api/reviews/TEST001", json={"action": action})
        assert response.status_code == 200
        assert response.json()["review_status"] == expected_status

    def test_review_action_stored(self, analyzed_content, client):
        client.post("/api/reviews/TEST001", json={"action": "approve"})
        content = client.get("/api/contents/TEST001").json()
        assert content["review_action"] == "approve"

    def test_comment_stored(self, analyzed_content, client):
        client.post(
            "/api/reviews/TEST001",
            json={"action": "hold", "comment": "추가 확인 필요"},
        )
        content = client.get("/api/contents/TEST001").json()
        assert content["reviewer_comment"] == "추가 확인 필요"

    def test_reviewed_at_is_set(self, analyzed_content, client):
        response = client.post("/api/reviews/TEST001", json={"action": "approve"})
        assert response.json()["reviewed_at"] is not None

    def test_review_without_comment(self, analyzed_content, client):
        response = client.post("/api/reviews/TEST001", json={"action": "remove"})
        assert response.status_code == 200
        assert response.json()["reviewer_comment"] is None

    def test_unknown_content_returns_404(self, client):
        response = client.post("/api/reviews/NONEXISTENT", json={"action": "approve"})
        assert response.status_code == 404

    def test_404_detail_mentions_content_id(self, client):
        response = client.post("/api/reviews/GHOST123", json={"action": "approve"})
        assert "GHOST123" in response.json()["detail"]

    def test_invalid_action_returns_422(self, analyzed_content, client):
        response = client.post("/api/reviews/TEST001", json={"action": "delete"})
        assert response.status_code == 422

    def test_missing_action_returns_422(self, analyzed_content, client):
        response = client.post("/api/reviews/TEST001", json={})
        assert response.status_code == 422
