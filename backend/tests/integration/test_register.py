class TestRegisterEndpoint:
    def test_returns_201_on_success(self, unauth_client):
        response = unauth_client.post("/register", json={"name": "홍길동"})
        assert response.status_code == 201

    def test_response_contains_required_fields(self, unauth_client):
        response = unauth_client.post("/register", json={"name": "홍길동"})
        data = response.json()
        assert "client_id" in data
        assert "client_name" in data
        assert "api_key" in data
        assert "key_prefix" in data

    def test_api_key_starts_with_cg(self, unauth_client):
        response = unauth_client.post("/register", json={"name": "홍길동"})
        assert response.json()["api_key"].startswith("cg-")

    def test_key_prefix_matches_api_key(self, unauth_client):
        response = unauth_client.post("/register", json={"name": "홍길동"})
        data = response.json()
        assert data["api_key"].startswith(data["key_prefix"])

    def test_client_name_matches_input(self, unauth_client):
        response = unauth_client.post("/register", json={"name": "홍길동"})
        assert response.json()["client_name"] == "홍길동"

    def test_duplicate_name_returns_400(self, unauth_client):
        unauth_client.post("/register", json={"name": "홍길동"})
        response = unauth_client.post("/register", json={"name": "홍길동"})
        assert response.status_code == 400
        assert "홍길동" in response.json()["detail"]

    def test_empty_name_returns_422(self, unauth_client):
        response = unauth_client.post("/register", json={"name": ""})
        assert response.status_code == 422

    def test_missing_name_returns_422(self, unauth_client):
        response = unauth_client.post("/register", json={})
        assert response.status_code == 422

    def test_issued_key_authenticates_successfully(self, unauth_client, mock_predict):
        reg = unauth_client.post("/register", json={"name": "홍길동"}).json()
        response = unauth_client.post(
            "/api/analyze",
            json={"content_id": "REG001", "text": "테스트"},
            headers={"Authorization": f"Bearer {reg['api_key']}"},
        )
        assert response.status_code == 201
