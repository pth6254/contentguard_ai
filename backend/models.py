
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from database import Base


class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(String, unique=True, index=True, nullable=False)
    text = Column(Text, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False)
    recommended_action = Column(String, nullable=False)
    explanation = Column(Text, nullable=True)
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
