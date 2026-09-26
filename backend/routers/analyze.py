import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from auth import get_client, get_client_or_operator
from config import settings
from database import get_db
from limiter import limiter
from models import Client, Content
from schemas import AnalyzeRequest, ContentResponse, ContentStatusResponse
from services.analysis_service import analyze_text
from services.content_service import save_analysis
from services.policy_service import load_policy
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze", response_model=ContentResponse, status_code=201)
@limiter.limit("60/hour")
def analyze(
    request: Request,
    body: AnalyzeRequest,
    db: Session = Depends(get_db),
    client: Optional[Client] = Depends(get_client_or_operator),
):
    client_id = client.id if client else None
    if db.query(Content).filter(Content.content_id == body.content_id, Content.client_id == client_id).first():
        raise HTTPException(status_code=400, detail=f"content_id '{body.content_id}' 는 이미 존재합니다.")
    analysis = analyze_text(body.text, policy=load_policy(db, client_id))
    try:
        return save_analysis(db=db, content_id=body.content_id, client_id=client_id, **analysis)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="동일한 콘텐츠 ID가 이미 처리되었습니다.")


@router.get("/contents/{content_id}/status", response_model=ContentStatusResponse)
def get_content_status(
    content_id: str,
    client: Client = Depends(get_client),
    db: Session = Depends(get_db),
):
    """클라이언트가 자신이 제출한 콘텐츠의 심사 상태를 조회합니다."""
    record = db.query(Content).filter(Content.content_id == content_id, Content.client_id == client.id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"content_id '{content_id}' 를 찾을 수 없습니다.")
    return record
