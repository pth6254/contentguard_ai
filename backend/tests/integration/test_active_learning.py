from tests.conftest import OPERATOR_SECRET


class TestActiveLearningAuth:
    def test_missing_secret_returns_401(self, unauth_client):
        response = unauth_client.get("/api/active-learning/candidates")
        assert response.status_code == 401

    def test_wrong_secret_returns_401(self, unauth_client):
        response = unauth_client.get(
            "/api/active-learning/candidates",
            headers={"x-admin-secret": "wrong"},
        )
        assert response.status_code == 401

    def test_correct_secret_returns_200(self, unauth_client):
        response = unauth_client.get(
            "/api/active-learning/candidates",
            headers={"x-admin-secret": OPERATOR_SECRET},
        )
        assert response.status_code == 200


class TestActiveLearningEndpoint:
    def test_returns_empty_when_no_reviews(self, client):
        response = client.get("/api/active-learning/candidates")
        assert response.status_code == 200
        assert response.json() == []

    def test_unreviewed_content_not_included(self, analyzed_content, client):
        # analyze만 하고 review 안 한 경우 → 후보 없음
        response = client.get("/api/active-learning/candidates?disagreement_only=false")
        assert response.status_code == 200
        assert response.json() == []

    def test_disagreement_included(self, analyzed_content, client):
        client.post("/api/reviews/TEST001", json={"action": "approve"})
        assert client.get("/api/active-learning/candidates").json() == []
        client.put(f"/api/evaluations/labels/{analyzed_content['id']}", json={"expected_level": "LOW", "category": "spam"})
        response = client.get("/api/active-learning/candidates")
        assert response.status_code == 200
        candidates = response.json()
        assert len(candidates) == 1
        assert candidates[0]["content_id"] == "TEST001"
        assert candidates[0]["content_record_id"] == analyzed_content["id"]
        assert candidates[0]["expected_level"] == "LOW"
        assert candidates[0]["disagreement"] is True

    def test_disagreement_candidate_fields(self, analyzed_content, client):
        client.post("/api/reviews/TEST001", json={"action": "approve"})
        client.put(f"/api/evaluations/labels/{analyzed_content['id']}", json={"expected_level": "LOW"})
        candidate = client.get("/api/active-learning/candidates").json()[0]
        assert candidate["model_risk_level"] == "CRITICAL"
        assert candidate["operator_level"] == "LOW"
        assert candidate["operator_action"] == "approve"
        assert candidate["suggested_score"] is None

    def test_agreement_excluded_when_disagreement_only(self, analyzed_content, client):
        client.post("/api/reviews/TEST001", json={"action": "remove"})
        client.put(f"/api/evaluations/labels/{analyzed_content['id']}", json={"expected_level": "CRITICAL"})
        response = client.get("/api/active-learning/candidates?disagreement_only=true")
        assert response.status_code == 200
        assert response.json() == []

    def test_agreement_included_when_disagreement_only_false(self, analyzed_content, client):
        client.post("/api/reviews/TEST001", json={"action": "remove"})
        client.put(f"/api/evaluations/labels/{analyzed_content['id']}", json={"expected_level": "CRITICAL"})
        response = client.get("/api/active-learning/candidates?disagreement_only=false")
        assert response.status_code == 200
        candidates = response.json()
        assert len(candidates) == 1
        assert candidates[0]["disagreement"] is False

    def test_enforcement_action_does_not_change_label(self, analyzed_content, client):
        client.put(f"/api/evaluations/labels/{analyzed_content['id']}", json={"expected_level": "HIGH"})
        for action in ("approve", "monitor", "hold", "remove"):
            client.post("/api/reviews/TEST001", json={"action": action})
            candidates = client.get(
                "/api/active-learning/candidates?disagreement_only=false"
            ).json()
            assert candidates[0]["operator_level"] == "HIGH"
            assert candidates[0]["suggested_score"] is None
