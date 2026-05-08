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


class ClientCreate(BaseModel):
    name: str = Field(..., example="쇼핑몰A")


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    created_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(..., example="production-key")


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None


class ApiKeyCreated(ApiKeyResponse):
    key: str  # 발급 직후 한 번만 반환


class CrawlRequest(BaseModel):
    url: str = Field(..., example="https://example.com/board/1234")
    max_items: int = Field(20, ge=1, le=50)


class UploadError(BaseModel):
    row: int
    content_id: str
    reason: str


class UploadResult(BaseModel):
    total: int
    saved: int
    skipped: int
    errors: list[UploadError]


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="홍길동")


class RegisterResponse(BaseModel):
    client_id: int
    client_name: str
    api_key: str  # 발급 직후 한 번만 반환
    key_prefix: str


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
