import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from auth import get_client_or_operator
from database import get_db
from limiter import limiter
from models import Client, Content
from schemas import AnalyzeRequest, ContentResponse
from services.content_service import save_analysis
from services.llm_service import generate_explanation
from services.prediction_service import prediction_service

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
    if db.query(Content).filter(Content.content_id == body.content_id).first():
        raise HTTPException(
            status_code=400,
            detail=f"content_id '{body.content_id}' 는 이미 존재합니다.",
        )

    all_predictions = prediction_service.predict_all(body.text)
    final = prediction_service.get_final_result(all_predictions)
    explanation = generate_explanation(
        text=body.text,
        risk_score=final["risk_score"],
        risk_level=final["risk_level"],
        recommended_action=final["recommended_action"],
    )
    return save_analysis(
        db=db,
        content_id=body.content_id,
        text=body.text,
        client_id=client.id if client else None,
        all_predictions=all_predictions,
        final=final,
        explanation=explanation,
    )
