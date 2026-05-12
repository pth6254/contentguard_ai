
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text

from database import Base


class Client(Base):
    __tablename__ = "clients"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, nullable=False, unique=True)
    email         = Column(String, nullable=True, unique=True, index=True)
    password_hash = Column(String, nullable=True)
    webhook_url   = Column(String, nullable=True)
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

    id        = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    content_id = Column(String, unique=True, index=True, nullable=False)
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
    review_action = Column(String, nullable=True)
    reviewer_comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ModelPrediction(Base):
    __tablename__ = "model_predictions"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(String, ForeignKey("contents.content_id"), nullable=False, index=True)

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
