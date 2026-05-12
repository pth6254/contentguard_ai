import logging
from typing import Optional

from sqlalchemy.orm import Session

from models import Content, ModelPrediction

logger = logging.getLogger(__name__)


def save_analysis(
    db: Session,
    content_id: str,
    text: str,
    client_id: Optional[int],
    all_predictions: list[dict],
    final: dict,
    explanation: Optional[str] = None,
    # v2 분석 세부 정보 (upload/crawl 라우터는 전달하지 않아도 됨)
    category_scores: Optional[dict] = None,
    triggered_rules: Optional[list] = None,
    evidence_spans: Optional[list] = None,
    explanation_json: Optional[dict] = None,
    raw_model_score: Optional[float] = None,
    calibrated_score: Optional[float] = None,
) -> Content:
    """예측 결과를 DB에 저장한다. 예측 실행과 LLM 호출은 호출자 책임."""

    record = Content(
        client_id=client_id,
        content_id=content_id,
        text=text,
        risk_score=final["risk_score"],
        risk_level=final["risk_level"],
        recommended_action=final["recommended_action"],
        explanation=explanation,
        # v2 필드
        raw_model_score=raw_model_score,
        calibrated_score=calibrated_score,
        category_scores=category_scores,
        triggered_rules=triggered_rules,
        evidence_spans=evidence_spans,
        explanation_json=explanation_json,
    )

    try:
        db.add(record)
        db.flush()
        db.bulk_insert_mappings(ModelPrediction, [
            {
                "content_id": content_id,
                "model_name": pred["model_name"],
                "model_version": pred["model_version"],
                "model_type": pred["model_type"],
                "risk_score": pred["risk_score"],
                "risk_level": pred["risk_level"],
                "recommended_action": pred["recommended_action"],
                "confidence": pred.get("confidence"),
                "latency_ms": pred.get("latency_ms"),
                "is_selected": pred["is_selected"],
                "is_shadow": pred["is_shadow"],
            }
            for pred in all_predictions
        ])
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        raise

    logger.info(
        "저장 완료: content_id=%s risk_level=%s score=%.3f models=%d",
        content_id, final["risk_level"], final["risk_score"], len(all_predictions),
    )
    return record
