import hashlib
import hmac
from datetime import datetime, timedelta

import httpx
from jose import jwt

from auth import hash_password
from config import settings
from models import ApiKey, Client, Content, Operator, ReviewEvent, WebhookDelivery
from services.webhook_service import deliver_one


def _signup_and_key(http, name):
    credentials = {"email": f"{name}@example.com", "password": "test-password-123"}
    signup = http.post("/auth/signup", json={"name": name, **credentials})
    assert signup.status_code == 201
    login = http.post("/auth/login", json=credentials)
    assert login.status_code == 200
    key = http.post("/auth/keys", json={"name": "test"},
                    headers={"Authorization": "Bearer " + login.json()["access_token"]})
    assert key.status_code == 201
    return {"Authorization": "Bearer " + key.json()["key"]}


def test_real_auth_and_tenant_scoped_content_ids(unauth_client, mock_predict):
    first = _signup_and_key(unauth_client, "tenant-a")
    second = _signup_and_key(unauth_client, "tenant-b")
    a = unauth_client.post("/api/analyze", headers=first, json={"content_id": "review-001", "text": "first"})
    b = unauth_client.post("/api/analyze", headers=second, json={"content_id": "review-001", "text": "second"})
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] != b.json()["id"]
    for headers in (first, second):
        assert unauth_client.get("/api/contents/review-001/status", headers=headers).status_code == 200
    unauth_client.post("/api/analyze", headers=first, json={"content_id": "private", "text": "first"})
    assert unauth_client.get("/api/contents/private/status", headers=second).status_code == 404


def test_ambiguous_operator_lookup_requires_record_id(client, db_session, mock_predict):
    first = client.post("/api/analyze", json={"content_id": "shared", "text": "first"}).json()
    other = Client(name="other")
    db_session.add(other)
    db_session.flush()
    db_session.add(Content(client_id=other.id, content_id="shared", text="second", risk_score=.1,
                           risk_level="LOW", recommended_action="APPROVE"))
    db_session.commit()
    assert client.get("/api/contents/shared").status_code == 409
    selected = client.get(f"/api/contents/shared?record_id={first['id']}")
    assert selected.status_code == 200 and selected.json()["text"] == "first"
    assert client.post("/api/reviews/shared", json={"action": "remove"}).status_code == 409


def test_delete_client_with_keys_and_content_policy(client, db_session, mock_predict):
    customer = client.post("/admin/clients", json={"name": "delete-me"}).json()
    client.post(f"/admin/clients/{customer['id']}/keys", json={"name": "key"})
    assert client.delete(f"/admin/clients/{customer['id']}").status_code == 204
    assert db_session.query(ApiKey).filter(ApiKey.client_id == customer["id"]).count() == 0
    client.post("/api/analyze", json={"content_id": "keep", "text": "keep"})
    assert client.delete("/admin/clients/1").status_code == 409


def test_operator_identity_history_and_optimistic_lock(unauth_client, db_session):
    operator = Operator(email="operator@example.com", name="Reviewer", password_hash=hash_password("test-password-123"))
    db_session.add(operator)
    record = Content(content_id="audit", text="text", risk_score=.1, risk_level="LOW", recommended_action="APPROVE")
    db_session.add(record)
    db_session.commit()
    token = unauth_client.post("/auth/operator/login", json={"email": operator.email, "password": "test-password-123"}).json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    url = f"/api/reviews/audit?record_id={record.id}"
    assert unauth_client.post(url, headers=headers, json={"action": "approve", "expected_version": 0}).status_code == 200
    assert unauth_client.post(url, headers=headers, json={"action": "remove", "expected_version": 0}).status_code == 409
    assert unauth_client.post(url, headers=headers, json={"action": "hold", "expected_version": 1}).status_code == 200
    events = db_session.query(ReviewEvent).order_by(ReviewEvent.version).all()
    assert len(events) == 2
    assert events[0].operator_id == operator.id
    assert events[1].previous_status == "APPROVED" and events[1].status == "HELD"


def test_malformed_signed_subject_returns_401(unauth_client):
    token = jwt.encode({"sub": "not-a-number", "role": "operator", "exp": datetime.utcnow() + timedelta(minutes=5)},
                       settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert unauth_client.get("/admin/clients", headers={"Authorization": "Bearer " + token}).status_code == 401


def _queued_delivery(client, db_session, analyzed_content):
    customer = db_session.get(Client, 1)
    customer.webhook_url = "https://receiver.example/webhook"
    db_session.commit()
    response = client.post("/api/reviews/TEST001", json={"action": "approve", "expected_version": 0})
    assert response.status_code == 200
    delivery = db_session.query(WebhookDelivery).one()
    assert delivery.status == "PENDING" and delivery.attempts == 0
    return delivery


def test_durable_webhook_retry_and_signature(client, db_session, analyzed_content):
    delivery = _queued_delivery(client, db_session, analyzed_content)
    event_id = delivery.id
    assert deliver_one(db_session, httpx.MockTransport(lambda request: httpx.Response(500)))
    db_session.refresh(delivery)
    assert delivery.status == "PENDING" and delivery.last_error == "HTTP 500"
    assert not deliver_one(db_session, httpx.MockTransport(lambda request: httpx.Response(200)))
    delivery.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()

    def receive(request):
        timestamp = request.headers["X-ContentGuard-Timestamp"]
        expected = hmac.new(delivery.secret.encode(), timestamp.encode() + b"." + request.content, hashlib.sha256).hexdigest()
        assert request.headers["X-ContentGuard-Signature"] == "sha256=" + expected
        assert request.headers["X-ContentGuard-Event"] == event_id
        return httpx.Response(200)

    assert deliver_one(db_session, httpx.MockTransport(receive))
    db_session.refresh(delivery)
    assert delivery.status == "DELIVERED" and delivery.attempts == 2


def test_webhook_final_failure_and_manual_retry(client, db_session, analyzed_content):
    delivery = _queued_delivery(client, db_session, analyzed_content)
    for _ in range(5):
        delivery.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
        db_session.commit()
        assert deliver_one(db_session, httpx.MockTransport(lambda request: httpx.Response(503)))
    assert delivery.status == "FAILED"
    assert client.post(f"/admin/webhooks/{delivery.id}/retry").status_code == 204
    db_session.refresh(delivery)
    assert delivery.status == "PENDING" and delivery.attempts == 0
