"""LLM 응답 검증 + fallback 단위 테스트."""
import pytest
from services.explanation_validator import (
    validate_explanation,
    build_fallback_explanation,
    REQUIRED_KEYS,
)

_VALID = {
    "summary": "테스트 요약입니다.",
    "score_explanation": "점수 설명입니다.",
    "main_reasons": ["이유1", "이유2"],
    "evidence": [
        {"quote": "씨발", "category": "profanity", "why_it_matters": "욕설"}
    ],
    "recommended_operator_check": "확인사항입니다.",
    "confidence_note": "확신도 높음",
}


class TestValidateExplanation:
    def test_valid_response_passes(self):
        ok, errors = validate_explanation(_VALID, "HIGH", 0.72, "씨발 나쁜 텍스트")
        assert ok
        assert errors == []

    def test_missing_key_fails(self):
        bad = {k: v for k, v in _VALID.items() if k != "summary"}
        ok, errors = validate_explanation(bad, "HIGH", 0.72, "텍스트")
        assert not ok
        assert any("summary" in str(e) for e in errors)

    def test_main_reasons_not_list_fails(self):
        bad = {**_VALID, "main_reasons": "이유입니다"}
        ok, errors = validate_explanation(bad, "HIGH", 0.72, "텍스트")
        assert not ok

    def test_evidence_not_list_fails(self):
        bad = {**_VALID, "evidence": "증거입니다"}
        ok, errors = validate_explanation(bad, "HIGH", 0.72, "텍스트")
        assert not ok

    def test_pii_in_explanation_fails(self):
        bad = {**_VALID, "summary": "전화번호는 010-1234-5678입니다"}
        ok, errors = validate_explanation(bad, "HIGH", 0.72, "텍스트")
        assert not ok
        assert any("PII" in e for e in errors)

    def test_email_pii_in_explanation_fails(self):
        bad = {**_VALID, "confidence_note": "연락처: test@example.com"}
        ok, errors = validate_explanation(bad, "HIGH", 0.72, "텍스트")
        assert not ok

    def test_empty_evidence_list_is_valid(self):
        with_empty = {**_VALID, "evidence": []}
        ok, errors = validate_explanation(with_empty, "HIGH", 0.72, "텍스트")
        assert ok

    def test_non_dict_input_fails(self):
        ok, errors = validate_explanation("not a dict", "HIGH", 0.72, "텍스트")
        assert not ok


class TestBuildFallbackExplanation:
    def _fallback(self, grade="HIGH", score=0.72):
        return build_fallback_explanation(
            final_grade=grade,
            final_score=score,
            category_scores={"profanity": 80, "threat": 50, "sexual": 0,
                             "privacy": 0, "spam": 0, "self_harm": 0, "policy_violation": 0},
            triggered_rules=[{"rule_id": "DIRECT_THREAT", "description": "협박 표현", "min_grade": "HIGH"}],
            recommended_action="REVIEW",
        )

    def test_fallback_has_all_required_keys(self):
        fallback = self._fallback()
        assert REQUIRED_KEYS <= set(fallback.keys())

    def test_fallback_summary_contains_score(self):
        fallback = self._fallback(score=0.72)
        assert "0.72" in fallback["summary"]

    def test_fallback_main_reasons_is_list(self):
        fallback = self._fallback()
        assert isinstance(fallback["main_reasons"], list)
        assert len(fallback["main_reasons"]) >= 1

    def test_fallback_evidence_is_list(self):
        fallback = self._fallback()
        assert isinstance(fallback["evidence"], list)

    def test_fallback_no_pii(self):
        fallback = self._fallback()
        full = " ".join(str(v) for v in fallback.values())
        assert "010-" not in full

    def test_fallback_is_valid(self):
        fallback = self._fallback()
        ok, errors = validate_explanation(fallback, "HIGH", 0.72, "마스킹된 텍스트")
        assert ok, f"fallback 검증 실패: {errors}"

    def test_fallback_critical_grade(self):
        fallback = build_fallback_explanation(
            "CRITICAL", 0.90,
            category_scores={"self_harm": 97, "profanity": 0, "threat": 0,
                             "sexual": 0, "privacy": 0, "spam": 0, "policy_violation": 0},
            triggered_rules=[],
            recommended_action="HOLD",
        )
        assert "CRITICAL" in fallback["summary"] or "심각" in fallback["summary"]
