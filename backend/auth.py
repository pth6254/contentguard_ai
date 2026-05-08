import hashlib

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import ApiKey, Client


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def get_client(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Client:
    """API 키 검증 후 Client 반환. 키가 없거나 유효하지 않으면 401."""
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

    from datetime import datetime
    api_key.last_used_at = datetime.utcnow()
    db.commit()

    client = db.query(Client).filter(Client.id == api_key.client_id).first()
    if not client:
        raise HTTPException(status_code=401, detail="클라이언트를 찾을 수 없습니다.")
    return client


def require_operator(x_admin_secret: str | None = Header(None)) -> None:
    """운영자 전용 엔드포인트 보호. X-Admin-Secret 헤더가 없거나 틀리면 401."""
    if not settings.ADMIN_SECRET:
        raise HTTPException(status_code=503, detail="ADMIN_SECRET이 설정되지 않았습니다.")
    if x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="운영자 인증이 필요합니다. X-Admin-Secret 헤더를 확인하세요.")


def get_client_or_operator(
    authorization: str | None = Header(None),
    x_admin_secret: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Client | None:
    """Bearer API 키 또는 X-Admin-Secret 중 하나를 허용.
    운영자로 인증된 경우 None 반환 (client_id 미설정), 클라이언트로 인증된 경우 Client 반환."""
    if x_admin_secret and settings.ADMIN_SECRET and x_admin_secret == settings.ADMIN_SECRET:
        return None

    if authorization and authorization.startswith("Bearer "):
        raw_key = authorization[7:].strip()
        key_hash = _hash_key(raw_key)
        api_key = (
            db.query(ApiKey)
            .filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
            .first()
        )
        if api_key:
            from datetime import datetime
            api_key.last_used_at = datetime.utcnow()
            db.commit()
            client = db.query(Client).filter(Client.id == api_key.client_id).first()
            if client:
                return client

    raise HTTPException(
        status_code=401,
        detail="API 키(Bearer) 또는 운영자 시크릿(X-Admin-Secret)이 필요합니다.",
    )
