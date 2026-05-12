"""강제 승격 규칙 적용 단위 테스트."""
import pytest
from services.decision_policy_service import apply_forced_escalation
from services.rule_detector import TriggeredRule


def _rule(rule_id: str, min_grade: str, category: str = "threat") -> TriggeredRule:
    return TriggeredRule(
        rule_id=rule_id,
        description="테스트 규칙",
        min_grade=min_grade,
        category=category,
        matched_text="테스트",
    )


class TestApplyForcedEscalation:
    def test_no_rules_keeps_base_grade(self):
        score, grade, action = apply_forced_escalation(0.15, [])
        assert grade == "LOW"
        assert score == pytest.approx(0.15, abs=0.001)

    def test_pii_rule_escalates_low_to_high(self):
        rule = _rule("PII_DETECTED", "HIGH", "privacy")
        score, grade, action = apply_forced_escalation(0.10, [rule])
        assert grade == "HIGH"
        assert score >= 0.60

    def test_self_harm_rule_escalates_to_critical(self):
        rule = _rule("SELF_HARM", "CRITICAL", "self_harm")
        score, grade, action = apply_forced_escalation(0.20, [rule])
        assert grade == "CRITICAL"
        assert score >= 0.85

    def test_already_high_grade_not_downgraded(self):
        # calibrated_score=0.95 이미 CRITICAL → HIGH 규칙이 있어도 유지
        rule = _rule("DIRECT_THREAT", "HIGH", "threat")
        score, grade, action = apply_forced_escalation(0.95, [rule])
        assert grade == "CRITICAL"

    def test_escalation_raises_score_to_grade_floor(self):
        # LOW(0.10) → HIGH 규칙 → 최소 0.60
        rule = _rule("PII_DETECTED", "HIGH", "privacy")
        score, grade, action = apply_forced_escalation(0.10, [rule])
        assert score >= 0.60

    def test_multiple_rules_take_highest_min_grade(self):
        rules = [
            _rule("PII_DETECTED", "HIGH", "privacy"),
            _rule("SELF_HARM", "CRITICAL", "self_harm"),
        ]
        score, grade, action = apply_forced_escalation(0.15, rules)
        assert grade == "CRITICAL"

    def test_recommended_action_matches_grade(self):
        _, grade, action = apply_forced_escalation(0.15, [])
        assert action == "APPROVE"  # LOW → APPROVE

        _, grade2, action2 = apply_forced_escalation(0.95, [])
        assert action2 == "HOLD"    # CRITICAL → HOLD

    def test_medium_score_no_rules(self):
        score, grade, action = apply_forced_escalation(0.45, [])
        assert grade == "MEDIUM"
        assert action == "MONITOR"
