import pytest
from services.decision_policy_service import classify_risk_level, get_recommended_action


class TestClassifyRiskLevel:
    @pytest.mark.parametrize("score,expected", [
        (0.00, "LOW"),
        (0.29, "LOW"),
        (0.30, "MEDIUM"),
        (0.59, "MEDIUM"),
        (0.60, "HIGH"),
        (0.84, "HIGH"),
        (0.85, "CRITICAL"),
        (1.00, "CRITICAL"),
    ])
    def test_boundary_values(self, score, expected):
        assert classify_risk_level(score) == expected

    def test_midpoint_medium(self):
        assert classify_risk_level(0.45) == "MEDIUM"

    def test_midpoint_high(self):
        assert classify_risk_level(0.72) == "HIGH"


class TestGetRecommendedAction:
    @pytest.mark.parametrize("level,expected", [
        ("LOW", "APPROVE"),
        ("MEDIUM", "MONITOR"),
        ("HIGH", "REVIEW"),
        ("CRITICAL", "HOLD"),
    ])
    def test_all_levels(self, level, expected):
        assert get_recommended_action(level) == expected


