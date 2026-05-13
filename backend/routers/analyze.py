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
from services.category_scorer import compute_category_scores
from services.content_service import save_analysis
from services.decision_policy_service import apply_forced_escalation
from services.evidence_service import extract_evidence_spans
from services.llm_service import classify_and_explain
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

    # ── 2. 카테고리 키워드 점수 (SAFE 게이트 + LLM 힌트용) ──────────────────
    category_hints = compute_category_scores(body.text)

    # ── 3. 규칙 탐지 ─────────────────────────────────────────────────────────
    triggered_rules_obj = detect_rules(body.text, detected_pii)
    triggered_rules = [r.to_dict() for r in triggered_rules_obj]

    # ── 4. LLM 1차 분류 + 설명 (NO_THINK 항상 활성) ─────────────────────────
    # 키워드 전부 0점 + 규칙 없으면 LLM 호출 생략 → SAFE 즉시 반환
    llm_result = classify_and_explain(masked_text, category_hints, triggered_rules)
    category_scores = llm_result["category_scores"]

    # ── 5. 강제 승격 규칙 적용 ───────────────────────────────────────────────
    final_score, final_grade, final_action = apply_forced_escalation(
        llm_result["risk_score"], triggered_rules_obj
    )
    final = {
        "risk_score": final_score,
        "risk_level": final_grade,
        "recommended_action": final_action,
    }

    # ── 6. Evidence span 추출 ─────────────────────────────────────────────────
    evidence_spans = extract_evidence_spans(masked_text, category_scores)

    # ── 7. HIGH/CRITICAL 심층 분석 (LLM_DEEP_ANALYSIS=true 시 활성) ──────────
    deep_analysis = None
    if settings.LLM_DEEP_ANALYSIS and final_grade in ("HIGH", "CRITICAL"):
        from services.deep_analysis import analyze_deeply
        deep_analysis = analyze_deeply(
            body.text, final_grade, category_scores, triggered_rules, evidence_spans
        )

    # ── 8. 설명 JSON 조립 ────────────────────────────────────────────────────
    explanation_json = {
        "summary":                    llm_result.get("summary", ""),
        "score_explanation":          llm_result.get("score_explanation", ""),
        "main_reasons":               llm_result.get("main_reasons", []),
        "evidence":                   llm_result.get("evidence", []),
        "recommended_operator_check": llm_result.get("recommended_operator_check", ""),
        "confidence_note":            llm_result.get("confidence_note", ""),
    }
    if deep_analysis:
        explanation_json["deep_analysis"] = deep_analysis

    # ── 9. DB 저장 ───────────────────────────────────────────────────────────
    return save_analysis(
        db=db,
        content_id=body.content_id,
        text=body.text,
        client_id=client.id if client else None,
        all_predictions=[],
        final=final,
        explanation=explanation_json.get("summary", ""),
        category_scores=category_scores,
        triggered_rules=triggered_rules,
        evidence_spans=evidence_spans,
        explanation_json=explanation_json,
        raw_model_score=None,
        calibrated_score=llm_result["risk_score"],
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
