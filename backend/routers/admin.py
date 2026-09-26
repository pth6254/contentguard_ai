import hashlib
import logging
import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from auth import get_current_operator
from database import get_db
from models import AnalysisJob, ApiKey, BatchImport, Client, ClientPolicy, Content, Operator, WebhookDelivery
from schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyResponse, ClientCreate, ClientResponse, ClientUpdate, WebhookUrlUpdate

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


@router.patch("/clients/{client_id}", response_model=ClientResponse,
              dependencies=[Depends(get_current_operator)])
def update_client(client_id: int, body: ClientUpdate, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="클라이언트를 찾을 수 없습니다.")
    if db.query(Client).filter(Client.name == body.name, Client.id != client_id).first():
        raise HTTPException(status_code=400, detail=f"이름 '{body.name}' 은 이미 사용 중입니다.")
    client.name = body.name
    db.commit()
    db.refresh(client)
    logger.info("클라이언트 이름 변경: id=%d name=%s", client_id, body.name)
    return client


@router.delete("/clients/{client_id}", status_code=204,
               dependencies=[Depends(get_current_operator)])
def delete_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="클라이언트를 찾을 수 없습니다.")
    if db.query(Content.id).filter(Content.client_id == client_id).first():
        raise HTTPException(status_code=409, detail="콘텐츠가 남아 있는 클라이언트는 삭제할 수 없습니다. 콘텐츠를 먼저 정리하세요.")
    if db.query(AnalysisJob.id).filter(AnalysisJob.client_id == client_id,
            AnalysisJob.status.in_(["PENDING", "PROCESSING"])).first():
        raise HTTPException(status_code=409, detail="진행 중인 분석 작업이 있습니다.")
    db.query(AnalysisJob).filter(AnalysisJob.client_id == client_id).delete()
    db.query(BatchImport).filter(BatchImport.client_id == client_id).delete()
    db.query(ClientPolicy).filter(ClientPolicy.client_id == client_id).delete()
    db.query(ApiKey).filter(ApiKey.client_id == client_id).delete(synchronize_session=False)
    db.delete(client)
    db.commit()
    logger.info("클라이언트 삭제: id=%d name=%s", client_id, client.name)


@router.patch("/clients/{client_id}/webhook", response_model=ClientResponse,
              dependencies=[Depends(get_current_operator)])
def update_webhook(client_id: int, body: WebhookUrlUpdate, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="클라이언트를 찾을 수 없습니다.")
    client.webhook_url = body.webhook_url
    db.commit()
    db.refresh(client)
    logger.info("웹훅 URL 업데이트: client_id=%d", client_id)
    return client


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


@router.get("/clients/{client_id}/webhook-secret", dependencies=[Depends(get_current_operator)])
def webhook_secret(client_id: int, response: Response, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="클라이언트를 찾을 수 없습니다.")
    response.headers["Cache-Control"] = "no-store"
    return {"secret": client.webhook_secret}


@router.get("/webhooks", dependencies=[Depends(get_current_operator)])
def webhook_deliveries(db: Session = Depends(get_db)):
    rows = db.query(WebhookDelivery).order_by(WebhookDelivery.next_attempt_at.desc()).limit(100).all()
    return [{"id": r.id, "review_event_id": r.review_event_id, "status": r.status,
             "attempts": r.attempts, "last_error": r.last_error,
             "next_attempt_at": r.next_attempt_at, "delivered_at": r.delivered_at} for r in rows]


@router.post("/webhooks/{delivery_id}/retry", status_code=204, dependencies=[Depends(get_current_operator)])
def retry_webhook(delivery_id: str, db: Session = Depends(get_db)):
    from datetime import datetime
    delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).with_for_update().first()
    if not delivery:
        raise HTTPException(status_code=404, detail="발송 기록을 찾을 수 없습니다.")
    if delivery.status != "FAILED":
        raise HTTPException(status_code=409, detail="최종 실패한 발송만 재시도할 수 있습니다.")
    delivery.status, delivery.attempts = "PENDING", 0
    delivery.next_attempt_at = datetime.utcnow()
    db.commit()
