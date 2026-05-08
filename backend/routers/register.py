import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from limiter import limiter
from models import ApiKey, Client
from schemas import RegisterRequest, RegisterResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["register"])


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/register", response_model=RegisterResponse, status_code=201)
@limiter.limit("5/hour")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    """이름만 입력하면 클라이언트 계정과 API 키를 즉시 발급합니다."""
    if db.query(Client).filter(Client.name == body.name).first():
        raise HTTPException(status_code=400, detail=f"이름 '{body.name}' 은 이미 사용 중입니다.")

    client = Client(name=body.name)
    db.add(client)
    db.flush()

    raw_key = f"cg-{secrets.token_hex(20)}"
    api_key = ApiKey(
        client_id=client.id,
        name="default",
        key_prefix=raw_key[:12],
        key_hash=_hash(raw_key),
    )
    db.add(api_key)
    db.commit()
    db.refresh(client)

    logger.info("자가 등록 완료: client_id=%d name=%s", client.id, client.name)
    return RegisterResponse(
        client_id=client.id,
        client_name=client.name,
        api_key=raw_key,
        key_prefix=raw_key[:12],
    )
