
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
    analysis_version = Column(Integer, nullable=False, default=1)
    needs_re_review = Column(Boolean, nullable=False, default=False)
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
    analysis_version = Column(Integer, nullable=True)
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


class AnalysisRun(Base):
    """One immutable result for each analysis or reanalysis."""
    __tablename__ = "analysis_runs"
    id = Column(Integer, primary_key=True)
    content_record_id = Column(Integer, ForeignKey("contents.id"), nullable=False, index=True)
    analysis_version = Column(Integer, nullable=False, default=0)
    source = Column(String(32), nullable=False, default="api")
    status = Column(String(16), nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(16), nullable=False)
    provider = Column(String(32), nullable=True)
    model = Column(String(100), nullable=True)
    prompt_version = Column(String(32), nullable=False, default="v1")
    policy_version = Column(String(32), nullable=False, default="v1")
    latency_ms = Column(Integer, nullable=True)
    category_scores = Column(JSON, nullable=True)
    explanation_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class EvaluationLabel(Base):
    """Explicit ground truth, independent of the operator's enforcement action."""
    __tablename__ = "evaluation_labels"
    id = Column(Integer, primary_key=True)
    content_record_id = Column(Integer, ForeignKey("contents.id"), nullable=False, unique=True, index=True)
    expected_level = Column(String(16), nullable=False)
    category = Column(String(40), nullable=True)
    reason = Column(Text, nullable=True)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AnalysisJob(Base):
    """Durable analysis request; input is masked before being stored."""
    __tablename__ = "analysis_jobs"
    id = Column(String(32), primary_key=True, default=lambda: secrets.token_hex(16))
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    batch_id = Column(String(32), ForeignKey("batch_imports.id"), nullable=True, index=True)
    submission_key = Column(String(255), nullable=True, unique=True)
    content_id = Column(String(200), nullable=False)
    content_record_id = Column(Integer, ForeignKey("contents.id"), nullable=True)
    text = Column(Text, nullable=False)
    pii_types = Column(JSON, nullable=False, default=list)
    kind = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, default="PENDING", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    lease_token = Column(String(32), nullable=True)
    last_error = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)


class ClientPolicy(Base):
    __tablename__ = "client_policies"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, unique=True)
    version = Column(Integer, nullable=False, default=1)
    category_min_levels = Column(JSON, nullable=False, default=dict)
    review_categories = Column(JSON, nullable=False, default=list)
    trigger_score = Column(Integer, nullable=False, default=60)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class BatchImport(Base):
    __tablename__ = "batch_imports"
    id = Column(String(32), primary_key=True, default=lambda: secrets.token_hex(16))
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    source_format = Column(String(8), nullable=False)
    rows_total = Column(Integer, nullable=False)
    accepted = Column(Integer, nullable=False)
    skipped = Column(Integer, nullable=False)
    errors = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    id = Column(String(32), primary_key=True)
    kind = Column(String(16), nullable=False, index=True)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    # Immutable label snapshots; no text or credentials are copied.
    items = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class EvaluationReport(Base):
    __tablename__ = "evaluation_reports"
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("evaluation_datasets.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    filters = Column(JSON, nullable=False)
    run_ids = Column(JSON, nullable=False)
    metrics = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
