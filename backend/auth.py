import hashlib
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import ApiKey, Client, Operator

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── 비밀번호 ───────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT ────────────────────────────────────────────────────────────────────

def create_access_token(sub: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": sub, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 토큰입니다.")


# ── API 키 인증 (분석·크롤링·업로드 엔드포인트용) ────────────────────────

def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def get_client(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Client:
    """Bearer API 키로 클라이언트 인증."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="API 키가 필요합니다. Authorization: Bearer <key>")

    raw_key = authorization[7:].strip()
    key_hash = _hash_key(raw_key)

    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
        .first()
    )
    if not api_key:
        raise HTTPException(status_code=401, detail="유효하지 않거나 비활성화된 API 키입니다.")

    api_key.last_used_at = datetime.utcnow()
    db.commit()

    client = db.query(Client).filter(Client.id == api_key.client_id).first()
    if not client:
        raise HTTPException(status_code=401, detail="클라이언트를 찾을 수 없습니다.")
    return client


# ── JWT 클라이언트 인증 (키 관리 엔드포인트용) ────────────────────────────

def get_current_client(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Client:
    """Bearer JWT로 클라이언트 인증."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    payload = _decode_jwt(authorization[7:].strip())
    if payload.get("role") != "client":
        raise HTTPException(status_code=403, detail="클라이언트 계정으로 접근하세요.")

    client = db.query(Client).filter(Client.id == int(payload["sub"])).first()
    if not client:
        raise HTTPException(status_code=401, detail="계정을 찾을 수 없습니다.")
    return client


# ── JWT 운영자 인증 ────────────────────────────────────────────────────────

def get_current_operator(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Operator:
    """Bearer JWT로 운영자 인증."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="운영자 로그인이 필요합니다.")

    payload = _decode_jwt(authorization[7:].strip())
    if payload.get("role") != "operator":
        raise HTTPException(status_code=403, detail="운영자 계정으로 접근하세요.")

    operator = db.query(Operator).filter(
        Operator.id == int(payload["sub"]),
        Operator.is_active == True,
    ).first()
    if not operator:
        raise HTTPException(status_code=401, detail="운영자 계정을 찾을 수 없습니다.")
    return operator


# ── 하위 호환: X-Admin-Secret 또는 JWT 운영자 토큰 모두 허용 ──────────────

def require_operator(
    authorization: str | None = Header(None),
    x_admin_secret: str | None = Header(None),
    db: Session = Depends(get_db),
) -> None:
    """운영자 전용 엔드포인트 보호. JWT 또는 X-Admin-Secret 중 하나를 허용."""
    if authorization and authorization.startswith("Bearer "):
        try:
            payload = _decode_jwt(authorization[7:].strip())
            if payload.get("role") == "operator":
                op = db.query(Operator).filter(
                    Operator.id == int(payload["sub"]),
                    Operator.is_active == True,
                ).first()
                if op:
                    return
        except HTTPException:
            pass

    if settings.ADMIN_SECRET and x_admin_secret == settings.ADMIN_SECRET:
        return

    raise HTTPException(status_code=401, detail="운영자 인증이 필요합니다.")


# ── API 키 또는 운영자 인증 (분석 엔드포인트용) ───────────────────────────

def get_client_or_operator(
    authorization: str | None = Header(None),
    x_admin_secret: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Client | None:
    """Bearer API 키 또는 운영자 인증(JWT / X-Admin-Secret) 중 하나를 허용.
    운영자로 인증된 경우 None 반환."""
    # 운영자 JWT
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        try:
            payload = _decode_jwt(token)
            if payload.get("role") == "operator":
                op = db.query(Operator).filter(
                    Operator.id == int(payload["sub"]),
                    Operator.is_active == True,
                ).first()
                if op:
                    return None
        except HTTPException:
            pass

    # 레거시 X-Admin-Secret
    if x_admin_secret and settings.ADMIN_SECRET and x_admin_secret == settings.ADMIN_SECRET:
        return None

    # 클라이언트 API 키
    if authorization and authorization.startswith("Bearer "):
        raw_key = authorization[7:].strip()
        key_hash = _hash_key(raw_key)
        api_key = (
            db.query(ApiKey)
            .filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
            .first()
        )
        if api_key:
            api_key.last_used_at = datetime.utcnow()
            db.commit()
            client = db.query(Client).filter(Client.id == api_key.client_id).first()
            if client:
                return client

    raise HTTPException(
        status_code=401,
        detail="API 키(Bearer) 또는 운영자 인증(Bearer JWT / X-Admin-Secret)이 필요합니다.",
    )
