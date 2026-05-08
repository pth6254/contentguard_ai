import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from auth import get_client_or_operator
from database import get_db
from limiter import limiter
from models import Client, Content, ModelPrediction
from typing import Optional
from schemas import AnalyzeRequest, ContentResponse
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

    record = Content(
        client_id=client.id if client else None,
        content_id=body.content_id,
        text=body.text,
        risk_score=final["risk_score"],
        risk_level=final["risk_level"],
        recommended_action=final["recommended_action"],
        explanation=explanation,
    )
    db.add(record)
    db.flush()

    for pred in all_predictions:
        db.add(ModelPrediction(
            content_id=body.content_id,
            model_name=pred["model_name"],
            model_version=pred["model_version"],
            model_type=pred["model_type"],
            risk_score=pred["risk_score"],
            risk_level=pred["risk_level"],
            recommended_action=pred["recommended_action"],
            confidence=pred.get("confidence"),
            latency_ms=pred.get("latency_ms"),
            is_selected=pred["is_selected"],
            is_shadow=pred["is_shadow"],
        ))

    db.commit()
    db.refresh(record)

    logger.info(
        "Saved content_id=%s with %d model prediction(s)",
        body.content_id,
        len(all_predictions),
    )
    return record
