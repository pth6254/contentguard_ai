import pytest
from services.risk_service import (
    analyze_content,
    calculate_risk_score,
    classify_risk_level,
    get_recommended_action,
)


class TestCalculateRiskScore:
    def test_no_keywords_returns_zero(self):
        assert calculate_risk_score("이 제품 정말 좋아요 배송 빠름") == 0.0

    def test_empty_string_returns_zero(self):
        assert calculate_risk_score("") == 0.0

    def test_single_keyword_사기(self):
        assert calculate_risk_score("이거 완전 사기임") == 0.4

    def test_single_keyword_쓰레기(self):
        assert calculate_risk_score("쓰레기 같은 제품") == 0.3

    def test_two_keywords_sum_weights(self):
        score = calculate_risk_score("사기 쓰레기")
        assert score == pytest.approx(0.7)

    def test_score_clamped_at_one(self):
        # 사기(0.4) + 쓰레기(0.3) + 최악(0.3) + 혐오(0.5) = 1.5 → clamped to 1.0
        score = calculate_risk_score("사기 쓰레기 최악 혐오")
        assert score == 1.0

    def test_keyword_substring_match(self):
        # '사기'는 '사기꾼' 안에 포함되므로 매칭됨
        assert calculate_risk_score("사기꾼이에요") == 0.4

    def test_광고_keyword(self):
        assert calculate_risk_score("이거 광고인가요?") == 0.2


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


class TestAnalyzeContent:
    def test_safe_text_returns_low(self):
        result = analyze_content("좋은 제품이에요 추천합니다")
        assert result["risk_level"] == "LOW"
        assert result["recommended_action"] == "APPROVE"
        assert result["risk_score"] == 0.0

    def test_keyword_text_returns_nonzero_score(self):
        result = analyze_content("완전 사기네요")
        assert result["risk_score"] > 0
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_result_has_required_keys(self):
        result = analyze_content("테스트")
        assert set(result.keys()) == {"risk_score", "risk_level", "recommended_action"}
