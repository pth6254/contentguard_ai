"""LLM 맥락 검토 서비스 단위 테스트."""
import json
import pytest
from unittest.mock import MagicMock, patch


def _make_client(response: dict | str):
    mock_client = MagicMock()
    raw = response if isinstance(response, str) else json.dumps(response)
    mock_client.chat.return_value = raw
    return mock_client


_CAT_SCORES = {
    "profanity": 80, "threat": 0, "sexual": 0,
    "privacy": 0, "spam": 0, "self_harm": 0, "policy_violation": 0,
}
_CLEAN_CATS = {k: 0 for k in _CAT_SCORES}
_RULES = [{"rule_id": "DIRECT_THREAT"}]


class TestReviewContext:
    def test_returns_modifier_and_note_on_success(self):
        with patch("services.llm_service._get_client", return_value=_make_client({"modifier": -0.20, "note": "부정문 표현"})):
            from services.context_review import review_context
            modifier, note = review_context("씨발 안 죽이겠다", _CAT_SCORES, _RULES)
        assert modifier == pytest.approx(-0.20, abs=0.001)
        assert note == "부정문 표현"

    def test_modifier_clamped_to_min(self):
        with patch("services.llm_service._get_client", return_value=_make_client({"modifier": -0.99, "note": "극단"})):
            from services.context_review import review_context
            modifier, _ = review_context("텍스트", _CAT_SCORES, [])
        assert modifier == pytest.approx(-0.30, abs=0.001)

    def test_modifier_clamped_to_max(self):
        with patch("services.llm_service._get_client", return_value=_make_client({"modifier": 0.50, "note": "양수"})):
            from services.context_review import review_context
            modifier, _ = review_context("텍스트", _CAT_SCORES, [])
        assert modifier == pytest.approx(0.0, abs=0.001)

    def test_zero_modifier_allowed(self):
        with patch("services.llm_service._get_client", return_value=_make_client({"modifier": 0.0, "note": "실제 위험"})):
            from services.context_review import review_context
            modifier, note = review_context("죽여버릴 거야", _CAT_SCORES, _RULES)
        assert modifier == pytest.approx(0.0, abs=0.001)
        assert note == "실제 위험"

    def test_llm_exception_returns_zero_modifier(self):
        mock_client = MagicMock()
        mock_client.chat.side_effect = RuntimeError("LLM 연결 실패")
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.context_review import review_context
            modifier, note = review_context("텍스트", _CAT_SCORES, [])
        assert modifier == 0.0
        assert note == ""

    def test_invalid_json_returns_zero_modifier(self):
        with patch("services.llm_service._get_client", return_value=_make_client("JSON이 아닌 텍스트")):
            from services.context_review import review_context
            modifier, note = review_context("텍스트", _CAT_SCORES, [])
        assert modifier == 0.0
        assert note == ""

    def test_json_missing_modifier_key_defaults_to_zero(self):
        with patch("services.llm_service._get_client", return_value=_make_client({"note": "키 없음"})):
            from services.context_review import review_context
            modifier, note = review_context("텍스트", _CAT_SCORES, [])
        assert modifier == 0.0
        assert note == "키 없음"

    def test_flagged_categories_appear_in_prompt(self):
        mock_client = _make_client({"modifier": 0.0, "note": ""})
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.context_review import review_context
            review_context("텍스트", _CAT_SCORES, _RULES)
        called_prompt = mock_client.chat.call_args[0][1]
        assert "profanity" in called_prompt

    def test_no_flagged_categories_uses_none_placeholder(self):
        mock_client = _make_client({"modifier": 0.0, "note": ""})
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.context_review import review_context
            review_context("텍스트", _CLEAN_CATS, [])
        called_prompt = mock_client.chat.call_args[0][1]
        assert "없음" in called_prompt

    def test_text_truncated_to_800_chars_in_prompt(self):
        long_text = "가" * 1000
        mock_client = _make_client({"modifier": 0.0, "note": ""})
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.context_review import review_context
            review_context(long_text, _CAT_SCORES, [])
        called_prompt = mock_client.chat.call_args[0][1]
        assert "가" * 801 not in called_prompt
