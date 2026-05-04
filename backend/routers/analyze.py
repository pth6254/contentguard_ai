import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Content
from schemas import AnalyzeRequest, ContentResponse
from services.llm_service import generate_explanation
from services.prediction_service import prediction_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze", response_model=ContentResponse, status_code=201)
def analyze(request: AnalyzeRequest, db: Session = Depends(get_db)):
    if db.query(Content).filter(Content.content_id == request.content_id).first():
        raise HTTPException(
            status_code=400,
            detail=f"content_id '{request.content_id}' 는 이미 존재합니다.",
        )

    result = prediction_service.predict(request.text)

    explanation = generate_explanation(
        text=request.text,
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        recommended_action=result["recommended_action"],
    )

    record = Content(
        content_id=request.content_id,
        text=request.text,
        explanation=explanation,
        **result,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info("Saved content_id=%s to DB", request.content_id)
    return record
