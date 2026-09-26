import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import require_operator
from database import get_db
from models import Content, EvaluationLabel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["active-learning"], dependencies=[Depends(require_operator)])

class ActiveLearningCandidate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    content_record_id: int
    client_id: int | None
    content_id: str
    text: str
    model_risk_level: str
    model_risk_score: float
    operator_action: str | None
    expected_level: str
    label_category: str | None
    operator_level: str | None
    suggested_score: float | None
    disagreement: bool


@router.get("/active-learning/candidates", response_model=list[ActiveLearningCandidate])
def get_candidates(
    disagreement_only: bool = Query(True, description="모델-운영자 불일치 건만 반환"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Explicitly labeled examples only; moderation action is never ground truth."""
    query = db.query(Content, EvaluationLabel).join(EvaluationLabel, EvaluationLabel.content_record_id == Content.id)
    if disagreement_only:
        query = query.filter(Content.risk_level != EvaluationLabel.expected_level)
    records = query.order_by(EvaluationLabel.updated_at.desc(), Content.id.desc()).offset(offset).limit(limit).all()

    candidates = []
    for r, label in records:
        operator_level = label.expected_level
        disagreement = operator_level != r.risk_level

        candidates.append(ActiveLearningCandidate(
            content_record_id=r.id,
            client_id=r.client_id,
            content_id=r.content_id,
            text=r.text,
            model_risk_level=r.risk_level,
            model_risk_score=r.risk_score,
            operator_action=r.review_action,
            expected_level=label.expected_level,
            label_category=label.category,
            operator_level=operator_level,
            suggested_score=None,
            disagreement=disagreement,
        ))

    logger.info(
        "Active learning candidates — total=%d disagreement_only=%s",
        len(candidates), disagreement_only,
    )
    return candidates
