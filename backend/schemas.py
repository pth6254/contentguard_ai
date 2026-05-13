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


class EvidenceSpan(BaseModel):
    text: str
    category: str
    severity: str
    start_index: int
    end_index: int


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

    # v2 분석 세부 정보 (신규 필드 — 기존 레코드는 null)
    raw_model_score:  Optional[float] = None
    calibrated_score: Optional[float] = None
    category_scores:  Optional[dict]  = None
    triggered_rules:  Optional[list]  = None
    evidence_spans:   Optional[list]  = None
    explanation_json: Optional[dict]  = None

    model_config = ConfigDict(from_attributes=True)


class ClientCreate(BaseModel):
    name: str = Field(..., example="쇼핑몰A")


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    webhook_url: Optional[str] = None
    created_at: datetime


class WebhookUrlUpdate(BaseModel):
    webhook_url: Optional[str] = Field(None, example="https://your-service.com/webhook")


class ClientUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="쇼핑몰B")


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



class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="홍길동")


class RegisterResponse(BaseModel):
    client_id: int
    client_name: str
    api_key: str  # 발급 직후 한 번만 반환
    key_prefix: str


# ── 인증 스키마 ────────────────────────────────────────────────────────────

class ClientSignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="홍길동")
    email: str = Field(..., example="user@example.com")
    password: str = Field(..., min_length=8, example="password123")


class LoginRequest(BaseModel):
    email: str = Field(..., example="user@example.com")
    password: str = Field(..., example="password123")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 초 단위


class ClientMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: Optional[str] = None
    created_at: datetime


class KeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="production-key")


class ContentStatusResponse(BaseModel):
    """클라이언트용 콘텐츠 심사 상태 응답 (내부 정보 제외)."""
    content_id: str
    risk_level: str
    risk_score: float
    review_status: str
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    by_level: dict[str, int]


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
