"""
최종 등급 결정 서비스.
ML 보정 점수에 규칙 기반 강제 승격을 적용해 final_score / final_grade를 결정한다.
LLM은 이 결과를 변경할 수 없다.
"""
import logging
from services.rule_detector import TriggeredRule

logger = logging.getLogger(__name__)

_GRADE_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
_GRADE_MIN_SCORE = {
    "LOW": 0.00, "MEDIUM": 0.30,
    "HIGH": 0.60, "CRITICAL": 0.85,
}


def classify_risk_level(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.60:
        return "HIGH"
    if score >= 0.30:
        return "MEDIUM"
    return "LOW"


def get_recommended_action(risk_level: str) -> str:
    return {"LOW": "APPROVE", "MEDIUM": "MONITOR", "HIGH": "REVIEW", "CRITICAL": "HOLD"}[risk_level]


def apply_forced_escalation(
    calibrated_score: float,
    triggered_rules: list[TriggeredRule],
) -> tuple[float, str, str]:
    """
    강제 승격 규칙을 적용해 최종 (score, grade, recommended_action)을 반환한다.
    등급이 올라가면 점수도 해당 등급의 최솟값으로 올린다.
    """
    base_grade = classify_risk_level(calibrated_score)
    final_grade = base_grade

    for rule in triggered_rules:
        min_idx = _GRADE_ORDER.index(rule.min_grade)
        cur_idx = _GRADE_ORDER.index(final_grade)
        if min_idx > cur_idx:
            logger.info(
                "강제 승격: %s → %s (rule=%s)",
                final_grade, rule.min_grade, rule.rule_id,
            )
            final_grade = rule.min_grade

    final_score = calibrated_score
    grade_floor = _GRADE_MIN_SCORE[final_grade]
    if final_score < grade_floor:
        final_score = grade_floor

    return round(final_score, 3), final_grade, get_recommended_action(final_grade)
