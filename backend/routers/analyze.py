import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Content, ModelPrediction
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

    all_predictions = prediction_service.predict_all(request.text)
    final = prediction_service.get_final_result(all_predictions)

    explanation = generate_explanation(
        text=request.text,
        risk_score=final["risk_score"],
        risk_level=final["risk_level"],
        recommended_action=final["recommended_action"],
    )

    record = Content(
        content_id=request.content_id,
        text=request.text,
        risk_score=final["risk_score"],
        risk_level=final["risk_level"],
        recommended_action=final["recommended_action"],
        explanation=explanation,
    )
    db.add(record)
    db.flush()

    for pred in all_predictions:
        db.add(ModelPrediction(
            content_id=request.content_id,
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
        request.content_id,
        len(all_predictions),
    )
    return record
