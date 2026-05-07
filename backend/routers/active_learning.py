import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from database import get_db
from models import Content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["active-learning"])

# 운영자 결정 → 위험 등급 / 재학습 점수 매핑
ACTION_TO_LEVEL = {
    "approve": "LOW",
    "monitor": "MEDIUM",
    "hold":    "HIGH",
    "remove":  "CRITICAL",
}

ACTION_TO_SCORE = {
    "approve": 0.10,
    "monitor": 0.44,
    "hold":    0.72,
    "remove":  0.92,
}


class ActiveLearningCandidate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    content_id: str
    text: str
    model_risk_level: str
    model_risk_score: float
    operator_action: str
    operator_level: str
    suggested_score: float
    disagreement: bool


@router.get("/active-learning/candidates", response_model=list[ActiveLearningCandidate])
def get_candidates(
    disagreement_only: bool = Query(True, description="모델-운영자 불일치 건만 반환"),
    db: Session = Depends(get_db),
):
    """
    운영자가 심사를 완료한 콘텐츠 중 재학습 후보를 반환한다.
    disagreement_only=True(기본)이면 모델 예측과 운영자 판단이 다른 건만 반환한다.
    """
    records = (
        db.query(Content)
        .filter(Content.review_action.isnot(None))
        .order_by(Content.reviewed_at.desc())
        .all()
    )

    candidates = []
    for r in records:
        operator_level = ACTION_TO_LEVEL.get(r.review_action, "")
        disagreement = operator_level != r.risk_level

        if disagreement_only and not disagreement:
            continue

        candidates.append(ActiveLearningCandidate(
            content_id=r.content_id,
            text=r.text,
            model_risk_level=r.risk_level,
            model_risk_score=r.risk_score,
            operator_action=r.review_action,
            operator_level=operator_level,
            suggested_score=ACTION_TO_SCORE[r.review_action],
            disagreement=disagreement,
        ))

    logger.info(
        "Active learning candidates — total=%d disagreement_only=%s",
        len(candidates), disagreement_only,
    )
    return candidates
