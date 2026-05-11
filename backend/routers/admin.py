import hashlib
import logging
import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_operator
from database import get_db
from models import ApiKey, Client, Operator
from schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyResponse, ClientCreate, ClientResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ── 클라이언트 관리 ────────────────────────────────────────────────────────

@router.post("/clients", response_model=ClientResponse, status_code=201,
             dependencies=[Depends(get_current_operator)])
def create_client(body: ClientCreate, db: Session = Depends(get_db)):
    if db.query(Client).filter(Client.name == body.name).first():
        raise HTTPException(status_code=400, detail=f"클라이언트 이름 '{body.name}' 이 이미 존재합니다.")
    client = Client(name=body.name)
    db.add(client)
    db.commit()
    db.refresh(client)
    logger.info("클라이언트 생성: id=%d name=%s", client.id, client.name)
    return client


@router.get("/clients", response_model=List[ClientResponse],
            dependencies=[Depends(get_current_operator)])
def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).order_by(Client.created_at.desc()).all()


# ── API 키 관리 (운영자가 특정 클라이언트 키 관리) ─────────────────────────

@router.post("/clients/{client_id}/keys", response_model=ApiKeyCreated, status_code=201,
             dependencies=[Depends(get_current_operator)])
def create_key(client_id: int, body: ApiKeyCreate, db: Session = Depends(get_db)):
    if not db.query(Client).filter(Client.id == client_id).first():
        raise HTTPException(status_code=404, detail="클라이언트를 찾을 수 없습니다.")

    raw_key = f"cg-{secrets.token_hex(20)}"
    api_key = ApiKey(
        client_id=client_id,
        name=body.name,
        key_prefix=raw_key[:12],
        key_hash=_hash(raw_key),
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    logger.info("API 키 발급: client_id=%d key_prefix=%s", client_id, api_key.key_prefix)
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


@router.get("/clients/{client_id}/keys", response_model=List[ApiKeyResponse],
            dependencies=[Depends(get_current_operator)])
def list_keys(client_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ApiKey)
        .filter(ApiKey.client_id == client_id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


@router.delete("/keys/{key_id}", status_code=204,
               dependencies=[Depends(get_current_operator)])
def revoke_key(key_id: int, db: Session = Depends(get_db)):
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API 키를 찾을 수 없습니다.")
    api_key.is_active = False
    db.commit()
    logger.info("API 키 비활성화: id=%d", key_id)


# ── 운영자 계정 목록 ───────────────────────────────────────────────────────

@router.get("/operators", response_model=List[dict],
            dependencies=[Depends(get_current_operator)])
def list_operators(db: Session = Depends(get_db)):
    ops = db.query(Operator).order_by(Operator.created_at.desc()).all()
    return [
        {"id": op.id, "email": op.email, "name": op.name,
         "is_active": op.is_active, "created_at": op.created_at}
        for op in ops
    ]
