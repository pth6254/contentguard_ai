from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    content_id: str = Field(..., example="C001")
    text: str = Field(..., min_length=1, example="이 제품 완전 사기네요")


class ReviewRequest(BaseModel):
    action: Literal["approve", "remove", "hold", "monitor"] = Field(
        ..., example="approve"
    )
    comment: Optional[str] = Field(None, example="검토 후 문제없음")


class ContentResponse(BaseModel):
    content_id: str
    text: str
    risk_score: float
    risk_level: str
    recommended_action: str
    explanation: Optional[str] = None
    review_status: str
    review_action: Optional[str] = None
    reviewer_comment: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelPredictionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)

    id: int
    content_id: str
    model_name: str
    model_version: str
    model_type: str
    risk_score: float
    risk_level: str
    recommended_action: str
    confidence: Optional[float] = None
    latency_ms: Optional[int] = None
    is_selected: bool
    is_shadow: bool
    created_at: datetime
