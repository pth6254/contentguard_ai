import hashlib
import logging
import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    get_current_client,
    get_current_operator,
    hash_password,
    verify_password,
)
from config import settings
from database import get_db
from limiter import limiter
from models import ApiKey, Client, Operator
from schemas import (
    ApiKeyCreated,
    ApiKeyResponse,
    ClientMeResponse,
    ClientSignupRequest,
    KeyCreateRequest,
    LoginRequest,
    TokenResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ── 클라이언트 회원가입 ────────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse, status_code=201)
@limiter.limit("5/hour")
def signup(request: Request, body: ClientSignupRequest, db: Session = Depends(get_db)):
    """이메일 + 비밀번호로 클라이언트 계정을 생성합니다."""
    if db.query(Client).filter(Client.name == body.name).first():
        raise HTTPException(status_code=400, detail=f"이름 '{body.name}' 은 이미 사용 중입니다.")
    if db.query(Client).filter(Client.email == body.email).first():
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")

    client = Client(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    token = create_access_token(sub=str(client.id), role="client")
    logger.info("클라이언트 가입: id=%d email=%s", client.id, client.email)
    return TokenResponse(access_token=token, expires_in=settings.JWT_EXPIRE_MINUTES * 60)


# ── 클라이언트 로그인 ──────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
@limiter.limit("20/hour")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    """이메일 + 비밀번호로 로그인합니다."""
    client = db.query(Client).filter(Client.email == body.email).first()
    if not client or not client.password_hash or not verify_password(body.password, client.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")

    token = create_access_token(sub=str(client.id), role="client")
    logger.info("클라이언트 로그인: id=%d", client.id)
    return TokenResponse(access_token=token, expires_in=settings.JWT_EXPIRE_MINUTES * 60)


# ── 운영자 로그인 ──────────────────────────────────────────────────────────

@router.post("/operator/login", response_model=TokenResponse)
@limiter.limit("20/hour")
def operator_login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    """운영자 이메일 + 비밀번호로 로그인합니다."""
    operator = db.query(Operator).filter(Operator.email == body.email, Operator.is_active == True).first()
    if not operator or not verify_password(body.password, operator.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")

    token = create_access_token(sub=str(operator.id), role="operator")
    logger.info("운영자 로그인: id=%d", operator.id)
    return TokenResponse(access_token=token, expires_in=settings.JWT_EXPIRE_MINUTES * 60)


# ── 내 계정 정보 ───────────────────────────────────────────────────────────

@router.get("/me", response_model=ClientMeResponse)
def me(client: Client = Depends(get_current_client)):
    return client


# ── 내 API 키 목록 ─────────────────────────────────────────────────────────

@router.get("/keys", response_model=List[ApiKeyResponse])
def list_my_keys(
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    return (
        db.query(ApiKey)
        .filter(ApiKey.client_id == client.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


# ── API 키 발급 ────────────────────────────────────────────────────────────

@router.post("/keys", response_model=ApiKeyCreated, status_code=201)
@limiter.limit("10/hour")
def create_my_key(
    request: Request,
    body: KeyCreateRequest,
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """로그인한 클라이언트가 직접 API 키를 발급합니다."""
    raw_key = f"cg-{secrets.token_hex(20)}"
    api_key = ApiKey(
        client_id=client.id,
        name=body.name,
        key_prefix=raw_key[:12],
        key_hash=_hash_key(raw_key),
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    logger.info("API 키 자가 발급: client_id=%d key_prefix=%s", client.id, api_key.key_prefix)
    return ApiKeyCreated(
        id=api_key.id,
        client_id=api_key.client_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        key=raw_key,
    )


# ── API 키 비활성화 ────────────────────────────────────────────────────────

@router.delete("/keys/{key_id}", status_code=204)
def revoke_my_key(
    key_id: int,
    client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """내 API 키를 비활성화합니다."""
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.client_id == client.id,
    ).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API 키를 찾을 수 없습니다.")
    api_key.is_active = False
    db.commit()
    logger.info("API 키 비활성화: id=%d client_id=%d", key_id, client.id)
