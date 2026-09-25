
from datetime import datetime
import secrets

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Index, UniqueConstraint, text as sql_text

from database import Base


class Client(Base):
    __tablename__ = "clients"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, nullable=False, unique=True)
    email         = Column(String, nullable=True, unique=True, index=True)
    password_hash = Column(String, nullable=True)
    webhook_url   = Column(String, nullable=True)
    webhook_secret = Column(String(64), nullable=False, default=lambda: secrets.token_hex(32))
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)


class Operator(Base):
    __tablename__ = "operators"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    name          = Column(String, nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id           = Column(Integer, primary_key=True, index=True)
    client_id    = Column(Integer, ForeignKey("clients.id"), nullable=False)
    name         = Column(String, nullable=False)
    key_prefix   = Column(String(16), nullable=False)   # 표시용 앞부분
    key_hash     = Column(String(64), nullable=False, unique=True)  # SHA-256
    is_active    = Column(Boolean, default=True, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)


class Content(Base):
    __tablename__ = "contents"
    __table_args__ = (
        UniqueConstraint("client_id", "content_id", name="uq_contents_client_content"),
        Index("uq_contents_operator_content", "content_id", unique=True,
              postgresql_where=sql_text("client_id IS NULL"), sqlite_where=sql_text("client_id IS NULL")),
    )

    id        = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    content_id = Column(String, index=True, nullable=False)
    text = Column(Text, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False)
    recommended_action = Column(String, nullable=False)
    explanation = Column(Text, nullable=True)
    # 분석 세부 정보 (v2 — nullable for backward compatibility)
    raw_model_score   = Column(Float, nullable=True)
    calibrated_score  = Column(Float, nullable=True)
    category_scores   = Column(JSON, nullable=True)   # {profanity:0-100, ...}
    triggered_rules   = Column(JSON, nullable=True)   # [{rule_id, description, ...}]
    evidence_spans    = Column(JSON, nullable=True)   # [{text, category, severity, ...}]
    explanation_json  = Column(JSON, nullable=True)   # LLM 구조화 출력 전체

    review_status = Column(String, nullable=False, default="PENDING")
    review_version = Column(Integer, nullable=False, default=0)
    review_action = Column(String, nullable=True)
    reviewer_comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ModelPrediction(Base):
    __tablename__ = "model_predictions"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(String, nullable=False, index=True)
    content_record_id = Column(Integer, ForeignKey("contents.id"), nullable=False, index=True)

    model_name = Column(String, nullable=False, index=True)
    model_version = Column(String, nullable=False, default="v1.0.0")
    model_type = Column(String, nullable=False, default="baseline")

    risk_score = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False)
    recommended_action = Column(String, nullable=False)

    confidence = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    is_selected = Column(Boolean, default=False)
    is_shadow = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)


class ReviewEvent(Base):
    """콘텐츠 삭제 후에도 변경 이력은 보존한다. 본문은 저장하지 않는다."""
    __tablename__ = "review_events"
    __table_args__ = (UniqueConstraint("content_record_id", "version", name="uq_review_event_version"),)
    id = Column(Integer, primary_key=True)
    content_record_id = Column(Integer, nullable=False, index=True)
    content_id = Column(String, nullable=False)
    client_id = Column(Integer, nullable=True)
    operator_id = Column(Integer, nullable=True)
    actor = Column(String, nullable=False)
    previous_status = Column(String, nullable=False)
    previous_action = Column(String, nullable=True)
    previous_comment = Column(Text, nullable=True)
    action = Column(String, nullable=False)
    status = Column(String, nullable=False)
    comment = Column(Text, nullable=True)
    version = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    id = Column(String(32), primary_key=True, default=lambda: secrets.token_hex(16))
    review_event_id = Column(Integer, ForeignKey("review_events.id"), nullable=False, unique=True)
    url = Column(Text, nullable=False)
    secret = Column(String(64), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="PENDING", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    last_error = Column(String, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
