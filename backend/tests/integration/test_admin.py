from tests.conftest import OPERATOR_SECRET


class TestAdminAuth:
    def test_missing_secret_returns_401(self, unauth_client):
        response = unauth_client.post("/admin/clients", json={"name": "테스트"})
        assert response.status_code == 401

    def test_wrong_secret_returns_401(self, unauth_client):
        response = unauth_client.post(
            "/admin/clients",
            json={"name": "테스트"},
            headers={"x-admin-secret": "wrong"},
        )
        assert response.status_code == 401


class TestAdminClients:
    def test_create_client_returns_201(self, client):
        response = client.post("/admin/clients", json={"name": "쇼핑몰A"})
        assert response.status_code == 201

    def test_create_client_response_fields(self, client):
        data = client.post("/admin/clients", json={"name": "쇼핑몰A"}).json()
        assert "id" in data
        assert data["name"] == "쇼핑몰A"
        assert "created_at" in data

    def test_duplicate_name_returns_400(self, client):
        client.post("/admin/clients", json={"name": "쇼핑몰A"})
        response = client.post("/admin/clients", json={"name": "쇼핑몰A"})
        assert response.status_code == 400
        assert "쇼핑몰A" in response.json()["detail"]

    def test_list_clients_returns_200(self, client):
        response = client.get("/admin/clients")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_clients_includes_created(self, client):
        client.post("/admin/clients", json={"name": "쇼핑몰A"})
        names = [c["name"] for c in client.get("/admin/clients").json()]
        assert "쇼핑몰A" in names


class TestAdminApiKeys:
    def _create_client(self, client):
        return client.post("/admin/clients", json={"name": "쇼핑몰A"}).json()

    def test_create_key_returns_201(self, client):
        c = self._create_client(client)
        response = client.post(f"/admin/clients/{c['id']}/keys", json={"name": "prod-key"})
        assert response.status_code == 201

    def test_create_key_returns_raw_key_once(self, client):
        c = self._create_client(client)
        data = client.post(f"/admin/clients/{c['id']}/keys", json={"name": "prod-key"}).json()
        assert "key" in data
        assert data["key"].startswith("cg-")

    def test_create_key_for_nonexistent_client_returns_404(self, client):
        response = client.post("/admin/clients/99999/keys", json={"name": "key"})
        assert response.status_code == 404

    def test_list_keys_returns_list(self, client):
        c = self._create_client(client)
        client.post(f"/admin/clients/{c['id']}/keys", json={"name": "prod-key"})
        response = client.get(f"/admin/clients/{c['id']}/keys")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_revoke_key_returns_204(self, client):
        c = self._create_client(client)
        key = client.post(f"/admin/clients/{c['id']}/keys", json={"name": "prod-key"}).json()
        response = client.delete(f"/admin/keys/{key['id']}")
        assert response.status_code == 204

    def test_revoked_key_is_inactive(self, client):
        c = self._create_client(client)
        key = client.post(f"/admin/clients/{c['id']}/keys", json={"name": "prod-key"}).json()
        client.delete(f"/admin/keys/{key['id']}")
        keys = client.get(f"/admin/clients/{c['id']}/keys").json()
        assert keys[0]["is_active"] is False

    def test_revoke_nonexistent_key_returns_404(self, client):
        response = client.delete("/admin/keys/99999")
        assert response.status_code == 404


class TestAdminClientUpdate:
    def _create_client(self, client):
        return client.post("/admin/clients", json={"name": "쇼핑몰A"}).json()

    def test_update_name_returns_200(self, client):
        c = self._create_client(client)
        response = client.patch(f"/admin/clients/{c['id']}", json={"name": "쇼핑몰B"})
        assert response.status_code == 200
        assert response.json()["name"] == "쇼핑몰B"

    def test_update_nonexistent_client_returns_404(self, client):
        response = client.patch("/admin/clients/99999", json={"name": "새이름"})
        assert response.status_code == 404

    def test_update_duplicate_name_returns_400(self, client):
        client.post("/admin/clients", json={"name": "쇼핑몰A"})
        c2 = client.post("/admin/clients", json={"name": "쇼핑몰B"}).json()
        response = client.patch(f"/admin/clients/{c2['id']}", json={"name": "쇼핑몰A"})
        assert response.status_code == 400

    def test_delete_client_returns_204(self, client):
        c = self._create_client(client)
        response = client.delete(f"/admin/clients/{c['id']}")
        assert response.status_code == 204

    def test_deleted_client_not_in_list(self, client):
        c = self._create_client(client)
        client.delete(f"/admin/clients/{c['id']}")
        names = [x["name"] for x in client.get("/admin/clients").json()]
        assert "쇼핑몰A" not in names

    def test_delete_nonexistent_client_returns_404(self, client):
        response = client.delete("/admin/clients/99999")
        assert response.status_code == 404
