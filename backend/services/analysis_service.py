"""API·크롤링에서 공유하는 분석 및 개인정보 처리 파이프라인."""
from config import settings
from services.category_scorer import compute_category_scores
from services.decision_policy_service import apply_forced_escalation
from services.evidence_service import extract_evidence_spans
from services.llm_service import classify_and_explain
from services.rule_detector import detect_rules, mask_pii


def redact(value):
    if isinstance(value, str):
        return mask_pii(value)[0]
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    return value


def analyze_text(text: str) -> dict:
    if not text.strip() or len(text) > 8000:
        raise ValueError("텍스트는 1~8,000자여야 합니다.")
    masked, pii = mask_pii(text)
    hints = compute_category_scores(text)
    rules = detect_rules(text, pii)
    rule_data = redact([rule.to_dict() for rule in rules])
    result = redact(classify_and_explain(masked, hints, rule_data))
    score, grade, action = apply_forced_escalation(result["risk_score"], rules)
    status = result.get("analysis_status", "completed")
    review_required = status != "completed" or any(r.review_only for r in rules)
    if review_required and action in ("APPROVE", "MONITOR"):
        action = "REVIEW"
    spans = extract_evidence_spans(masked, result["category_scores"])
    explanation = {key: result.get(key, [] if key in ("main_reasons", "evidence") else "")
                   for key in ("summary", "score_explanation", "main_reasons", "evidence",
                               "recommended_operator_check", "confidence_note")}
    explanation.update(analysis_status=status, review_required=review_required,
                       model_risk_level=result["risk_level"], final_risk_level=grade)
    if grade != result["risk_level"]:
        reason = ", ".join(r.rule_id for r in rules if not r.review_only)
        note = f"규칙({reason})에 따라 최종 등급을 {grade}로 상향했습니다."
        explanation["summary"] = note + " " + explanation["summary"]
        explanation["score_explanation"] = note + " " + explanation["score_explanation"]
    if review_required:
        explanation["recommended_operator_check"] = "운영자 직접 검토 필요. " + explanation["recommended_operator_check"]
    if settings.LLM_DEEP_ANALYSIS and grade in ("HIGH", "CRITICAL"):
        from services.deep_analysis import analyze_deeply
        deep = analyze_deeply(masked, grade, result["category_scores"], rule_data, spans)
        if deep:
            explanation["deep_analysis"] = redact(deep)
    return dict(text=masked, all_predictions=[],
                final={"risk_score": score, "risk_level": grade, "recommended_action": action},
                explanation=explanation["summary"], explanation_json=explanation,
                category_scores=result["category_scores"], triggered_rules=rule_data,
                evidence_spans=spans, calibrated_score=result["risk_score"])
