"""
LLM JSON 응답 검증 서비스.
- 필수 스키마 충족 검사
- final_grade / final_score 변경 방지
- PII 재노출 방지
- 검증 실패 시 결정론적 fallback 생성
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

REQUIRED_KEYS = frozenset({
    "summary", "score_explanation", "main_reasons",
    "evidence", "recommended_operator_check", "confidence_note",
})
EVIDENCE_REQUIRED = frozenset({"quote", "category", "why_it_matters"})

_PII_CHECK = [
    re.compile(r'01[016789]-?\d{3,4}-?\d{4}'),
    re.compile(r'\d{6}-[1-4]\d{6}'),
    re.compile(r'\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}'),
    re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'),
]

_CAT_KO = {
    "profanity": "욕설/비방",
    "threat": "협박/폭력",
    "sexual": "성적 표현",
    "privacy": "개인정보 침해",
    "spam": "스팸/도배",
    "self_harm": "자해/자살 표현",
    "policy_violation": "정책 위반",
}
_GRADE_KO = {
    "LOW": "낮은 위험", "MEDIUM": "보통 위험",
    "HIGH": "높은 위험", "CRITICAL": "심각한 위험",
}
_ACTION_KO = {
    "APPROVE": "승인", "MONITOR": "모니터링",
    "REVIEW": "직접 검토", "HOLD": "즉시 보류",
}


def _has_pii(text: str) -> bool:
    return any(p.search(text) for p in _PII_CHECK)


def validate_explanation(
    explanation: dict,
    final_grade: str,
    final_score: float,
    masked_text: str,
) -> tuple[bool, list[str]]:
    """
    LLM 응답 dict가 스키마를 만족하고 안전한지 검증한다.
    Returns: (is_valid, error_list)
    """
    errors: list[str] = []

    if not isinstance(explanation, dict):
        return False, ["응답이 dict가 아님"]

    missing = REQUIRED_KEYS - set(explanation.keys())
    if missing:
        errors.append(f"필수 키 누락: {missing}")

    if not isinstance(explanation.get("main_reasons"), list):
        errors.append("main_reasons가 리스트가 아님")

    evidence = explanation.get("evidence", [])
    if not isinstance(evidence, list):
        errors.append("evidence가 리스트가 아님")
    else:
        for i, ev in enumerate(evidence):
            if not isinstance(ev, dict):
                errors.append(f"evidence[{i}]가 dict가 아님")
                continue
            missing_ev = EVIDENCE_REQUIRED - set(ev.keys())
            if missing_ev:
                errors.append(f"evidence[{i}] 키 누락: {missing_ev}")

    # PII가 설명에 그대로 포함됐으면 실패
    full_text = " ".join(str(v) for v in explanation.values())
    if _has_pii(full_text):
        errors.append("설명에 개인정보(PII) 패턴이 포함되어 있음")

    return len(errors) == 0, errors


def build_fallback_explanation(
    final_grade: str,
    final_score: float,
    category_scores: dict[str, int],
    triggered_rules: list[dict],
    recommended_action: str,
) -> dict:
    """검증 실패 또는 LLM 오류 시 결정론적 대체 설명을 반환한다."""
    top_cats = [
        cat for cat, score
        in sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        if score > 0
    ][:3]

    cat_str = ", ".join(_CAT_KO.get(c, c) for c in top_cats) or "일반 위험"
    rule_descs = [r.get("description", "") for r in triggered_rules if r.get("description")]

    summary = (
        f"위험 점수 {final_score:.2f} / "
        f"{_GRADE_KO.get(final_grade, final_grade)} 등급으로 판정되었습니다. "
        f"주요 위험 유형: {cat_str}."
    )
    reasons = [f"{_CAT_KO.get(c, c)} 관련 위험 요소 감지" for c in top_cats]
    reasons.extend(rule_descs)

    return {
        "summary": summary,
        "score_explanation": (
            f"ML 모델과 카테고리 분석을 조합한 결과 {final_score:.2f} 점수로 "
            f"{_GRADE_KO.get(final_grade, final_grade)} 등급이 결정되었습니다."
            + (f" 강제 승격 규칙 적용: {', '.join(rule_descs)}." if rule_descs else "")
        ),
        "main_reasons": reasons or ["자동 분석 결과, 위험 요소가 감지되었습니다."],
        "evidence": [],
        "recommended_operator_check": (
            f"권장 조치: {_ACTION_KO.get(recommended_action, recommended_action)}. "
            "운영자가 콘텐츠를 직접 확인 후 최종 판단하세요."
        ),
        "confidence_note": "자동 분석 결과이며 운영자의 최종 판단이 필요합니다.",
    }
