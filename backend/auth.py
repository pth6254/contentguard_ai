import hashlib

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

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
