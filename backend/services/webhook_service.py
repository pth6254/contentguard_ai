"""Durable, at-least-once webhook delivery with a lease and bounded retries."""
import hashlib
import hmac
import time
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session
from models import WebhookDelivery

MAX_ATTEMPTS = 5


def signature(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def deliver_one(db: Session, transport=None) -> bool:
    now = datetime.utcnow()
    delivery = (db.query(WebhookDelivery)
                .filter(WebhookDelivery.status.in_(["PENDING", "PROCESSING"]),
                        WebhookDelivery.next_attempt_at <= now)
                .order_by(WebhookDelivery.next_attempt_at, WebhookDelivery.id)
                .with_for_update(skip_locked=True).first())
    if delivery is None:
        db.rollback()
        return False
    if delivery.attempts >= MAX_ATTEMPTS:
        delivery.status = "FAILED"
        delivery.last_error = "Delivery lease expired after final attempt"
        db.commit()
        return True
    delivery.status = "PROCESSING"
    delivery.attempts += 1
    delivery.next_attempt_at = now + timedelta(seconds=60)
    db.commit()
    timestamp = str(int(time.time()))
    payload = delivery.body.encode("utf-8")
    try:
        with httpx.Client(timeout=5.0, follow_redirects=False, transport=transport) as client:
            response = client.post(delivery.url, content=payload, headers={
                "Content-Type": "application/json", "X-ContentGuard-Event": delivery.id,
                "X-ContentGuard-Timestamp": timestamp,
                "X-ContentGuard-Signature": "sha256=" + signature(delivery.secret, timestamp, payload),
            })
            response.raise_for_status()
        delivery.status = "DELIVERED"
        delivery.delivered_at = datetime.utcnow()
        delivery.last_error = None
    except Exception as exc:
        delivery.last_error = (f"HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError)
                               else type(exc).__name__)
        delivery.status = "FAILED" if delivery.attempts >= MAX_ATTEMPTS else "PENDING"
        delivery.next_attempt_at = datetime.utcnow() + timedelta(seconds=min(3600, 5 * 2 ** delivery.attempts))
    db.commit()
    return True
