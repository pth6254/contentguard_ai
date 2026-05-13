"""카테고리별 점수 산정 단위 테스트."""
import pytest
from services.category_scorer import (
    compute_category_scores,
    compute_calibrated_score,
    CATEGORIES,
)


class TestComputeCategoryScores:
    def test_returns_all_categories(self):
        scores = compute_category_scores("테스트 텍스트")
        assert set(scores.keys()) == set(CATEGORIES)

    def test_scores_are_0_to_100(self):
        scores = compute_category_scores("씨발 죽여버릴 자살")
        for cat, score in scores.items():
            assert 0 <= score <= 100, f"{cat}={score} 범위 초과"

    def test_profanity_detected(self):
        scores = compute_category_scores("씨발 이 새끼야")
        assert scores["profanity"] > 0

    def test_threat_detected(self):
        scores = compute_category_scores("죽여버릴 거야")
        assert scores["threat"] >= 90

    def test_self_harm_detected(self):
        scores = compute_category_scores("자살할 거야")
        assert scores["self_harm"] >= 90

    def test_clean_text_all_zero(self):
        scores = compute_category_scores("오늘 날씨가 정말 좋네요")
        assert all(v == 0 for v in scores.values())

    def test_sexual_detected(self):
        scores = compute_category_scores("강간 위협 내용")
        assert scores["sexual"] >= 90

    def test_spam_detected(self):
        scores = compute_category_scores("도배 광고 클릭하세요")
        assert scores["spam"] > 0

    def test_multiple_categories_independent(self):
        scores = compute_category_scores("씨발 사기꾼")
        assert scores["profanity"] > 0
        assert scores["policy_violation"] > 0

    def test_year_number_not_flagged_as_profanity(self):
        # "2-3년" 의 "년"은 기간 맥락 — profanity 오탐 방지
        scores = compute_category_scores("2-3년 정도 걸립니다")
        assert scores["profanity"] <= 17  # 감쇄 적용 시 최대 0.50×0.35×100 = 17

    def test_slur_neon_still_detected(self):
        # 욕설로 쓰인 "년"은 여전히 감지
        scores = compute_category_scores("이 년아 꺼져")
        assert scores["profanity"] > 17


class TestComputeCalibratedScore:
    def test_clean_text_score_equals_model_score(self):
        cat_scores = {c: 0 for c in CATEGORIES}
        calibrated = compute_calibrated_score(0.5, cat_scores)
        # 카테고리 최고점 0 → 0.7 × 0.5 + 0.3 × 0.0 = 0.35
        assert calibrated == pytest.approx(0.35, abs=0.01)

    def test_high_category_score_raises_calibrated(self):
        cat_scores = {c: 0 for c in CATEGORIES}
        cat_scores["threat"] = 97
        calibrated = compute_calibrated_score(0.3, cat_scores)
        # 0.7 × 0.3 + 0.3 × 0.97 = 0.21 + 0.291 = 0.501
        assert calibrated > 0.3

    def test_calibrated_score_never_exceeds_1(self):
        cat_scores = {c: 100 for c in CATEGORIES}
        calibrated = compute_calibrated_score(1.0, cat_scores)
        assert calibrated <= 1.0

    def test_calibrated_score_never_below_0(self):
        cat_scores = {c: 0 for c in CATEGORIES}
        calibrated = compute_calibrated_score(0.0, cat_scores)
        assert calibrated >= 0.0
