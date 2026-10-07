"""Operator-managed customer policies with optimistic versioning and preview."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_operator
from database import get_db
from models import Client, ClientPolicy, Content
from services.category_scorer import KEYWORDS
from services.policy_service import apply_policy, base_decision

router = APIRouter(prefix="/api/policies", tags=["policies"], dependencies=[Depends(get_current_operator)])


class PolicyRequest(BaseModel):
    expected_version: int = Field(0, ge=0)
    category_min_levels: dict[str, Literal["MEDIUM", "HIGH", "CRITICAL"]] = Field(default_factory=dict)
    review_categories: list[str] = Field(default_factory=list)
    trigger_score: int = Field(60, ge=1, le=100)

    @model_validator(mode="after")
    def valid_categories(self):
        unknown = (set(self.category_min_levels) | set(self.review_categories)) - set(KEYWORDS)
        if unknown:
            raise ValueError("알 수 없는 위험 유형: " + ", ".join(sorted(unknown)))
        return self


def _present(policy: ClientPolicy | None, client_id: int) -> dict:
    return {"client_id": client_id, "version": policy.version if policy else 0,
            "category_min_levels": policy.category_min_levels if policy else {},
            "review_categories": policy.review_categories if policy else [],
            "trigger_score": policy.trigger_score if policy else 60,
            "updated_at": policy.updated_at if policy else None}


@router.get("/{client_id}")
def get_policy(client_id: int, db: Session = Depends(get_db)):
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="고객이 없습니다.")
    return _present(db.query(ClientPolicy).filter(ClientPolicy.client_id == client_id).first(), client_id)


@router.put("/{client_id}")
def update_policy(client_id: int, body: PolicyRequest, db: Session = Depends(get_db)):
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="고객이 없습니다.")
    policy = db.query(ClientPolicy).filter(ClientPolicy.client_id == client_id).with_for_update().first()
    version = policy.version if policy else 0
    if body.expected_version != version:
        raise HTTPException(status_code=409, detail="다른 운영자가 정책을 변경했습니다. 다시 조회하세요.")
    if policy is None:
        policy = ClientPolicy(client_id=client_id)
        db.add(policy)
    policy.version = version + 1
    policy.category_min_levels = body.category_min_levels
    policy.review_categories = sorted(set(body.review_categories))
    policy.trigger_score = body.trigger_score
    policy.updated_at = datetime.utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="다른 운영자가 정책을 먼저 저장했습니다. 다시 조회하세요.")
    return _present(policy, client_id)


@router.post("/{client_id}/preview")
def preview_policy(client_id: int, body: PolicyRequest, db: Session = Depends(get_db)):
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="고객이 없습니다.")
    policy = {"version": body.expected_version + 1, "category_min_levels": body.category_min_levels,
              "review_categories": body.review_categories, "trigger_score": body.trigger_score}
    records = (db.query(Content).filter(Content.client_id == client_id)
               .order_by(Content.id.desc()).limit(100).all())
    changes = []
    skipped = 0
    for record in records:
        base = base_decision(record)
        if not record.category_scores or base is None:
            skipped += 1
            continue
        _, grade, action, review, _ = apply_policy(base["risk_score"], base["risk_level"],
                                                   record.category_scores, policy)
        review = review or base["review_required"]
        if review and action in ("APPROVE", "MONITOR"):
            action = "REVIEW"
        if grade != record.risk_level or action != record.recommended_action or review != bool((record.explanation_json or {}).get("review_required")):
            changes.append({"record_id": record.id, "content_id": record.content_id,
                            "before": record.risk_level, "after": grade,
                            "recommended_action": action,
                            "review_required": review})
    return {"sampled": len(records), "skipped": skipped, "changed": len(changes), "changes": changes,
            "notice": "기존 결과는 바뀌지 않습니다. 새 분석 또는 재분석에 적용됩니다."}
