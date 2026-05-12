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
from services.category_scorer import compute_category_scores, compute_calibrated_score
from services.content_service import save_analysis
from services.decision_policy_service import apply_forced_escalation
from services.evidence_service import extract_evidence_spans
from services.llm_service import generate_explanation, generate_explanation_json
from services.prediction_service import prediction_service
from services.rule_detector import mask_pii, detect_rules

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

    # ── 1. PII 마스킹 ────────────────────────────────────────────────────────
    masked_text, detected_pii = mask_pii(body.text)

    # ── 2. ML 모델 예측 ──────────────────────────────────────────────────────
    all_predictions = prediction_service.predict_all(body.text)
    ml_result = prediction_service.get_final_result(all_predictions)
    raw_model_score = ml_result["risk_score"]

    # ── 3. 카테고리별 점수 산정 (부정어·무해 맥락 감쇄 포함) ─────────────────
    category_scores = compute_category_scores(body.text)

    # ── 4. 보정 점수 (ML × w + 카테고리 max × w) ─────────────────────────────
    calibrated_score = compute_calibrated_score(raw_model_score, category_scores)

    # ── 5. 규칙 탐지 ─────────────────────────────────────────────────────────
    triggered_rules_obj = detect_rules(body.text, detected_pii)
    triggered_rules = [r.to_dict() for r in triggered_rules_obj]

    # ── 6. LLM 맥락 검토 (LLM_CONTEXT_REVIEW=true 시 활성) ───────────────────
    context_note = ""
    if settings.LLM_CONTEXT_REVIEW:
        from services.context_review import review_context
        context_modifier, context_note = review_context(
            body.text, category_scores, triggered_rules
        )
        if context_modifier < 0:
            calibrated_score = round(
                max(0.0, min(1.0, calibrated_score + context_modifier)), 3
            )
            logger.info(
                "Context review 적용 — modifier=%.3f → calibrated_score=%.3f",
                context_modifier, calibrated_score,
            )

    # ── 7. 강제 승격 규칙 적용 ───────────────────────────────────────────────
    final_score, final_grade, final_action = apply_forced_escalation(
        calibrated_score, triggered_rules_obj
    )

    final = {
        "risk_score": final_score,
        "risk_level": final_grade,
        "recommended_action": final_action,
    }

    # ── 8. Evidence span 추출 ─────────────────────────────────────────────────
    evidence_spans = extract_evidence_spans(masked_text, category_scores)

    # ── 9. LLM 구조화 설명 생성 ──────────────────────────────────────────────
    explanation_json = generate_explanation_json(
        masked_text=masked_text,
        final_score=final_score,
        final_grade=final_grade,
        recommended_action=final_action,
        category_scores=category_scores,
        triggered_rules=triggered_rules,
        evidence_spans=evidence_spans,
        context_note=context_note,
    )
    explanation = explanation_json.get("summary", "")

    # ── 10. DB 저장 ───────────────────────────────────────────────────────────
    return save_analysis(
        db=db,
        content_id=body.content_id,
        text=body.text,
        client_id=client.id if client else None,
        all_predictions=all_predictions,
        final=final,
        explanation=explanation,
        category_scores=category_scores,
        triggered_rules=triggered_rules,
        evidence_spans=evidence_spans,
        explanation_json=explanation_json,
        raw_model_score=raw_model_score,
        calibrated_score=calibrated_score,
    )


@router.get("/contents/{content_id}/status", response_model=ContentStatusResponse)
def get_content_status(
    content_id: str,
    client: Client = Depends(get_client),
    db: Session = Depends(get_db),
):
    """클라이언트가 자신이 제출한 콘텐츠의 심사 상태를 조회합니다."""
    record = db.query(Content).filter(Content.content_id == content_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"content_id '{content_id}' 를 찾을 수 없습니다.")
    if record.client_id != client.id:
        raise HTTPException(status_code=403, detail="해당 콘텐츠에 접근 권한이 없습니다.")
    return record
