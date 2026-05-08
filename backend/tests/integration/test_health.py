class TestHealth:
    def test_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_contains_status_field(self, client):
        data = client.get("/health").json()
        assert "status" in data

    def test_contains_db_field(self, client):
        data = client.get("/health").json()
        assert "db" in data

    def test_contains_ollama_field(self, client):
        data = client.get("/health").json()
        assert "ollama" in data

    def test_db_is_ok_in_test_env(self, client):
        data = client.get("/health").json()
        assert data["db"] == "ok"

    def test_status_degraded_when_dependency_fails(self, client):
        from unittest.mock import patch
        with patch("sqlalchemy.engine.base.Connection.execute", side_effect=Exception("DB 연결 실패")):
            data = client.get("/health").json()
        assert data["status"] == "degraded"
