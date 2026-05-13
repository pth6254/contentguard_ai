"""MEDIUM 구간 LLM tiebreaker 서비스 단위 테스트."""
import json
import pytest
from unittest.mock import MagicMock, patch


def _make_client(response: dict | str):
    mock_client = MagicMock()
    raw = response if isinstance(response, str) else json.dumps(response)
    mock_client.chat.return_value = raw
    return mock_client


_CAT_SCORES = {
    "profanity": 50, "threat": 30, "sexual": 0,
    "privacy": 0, "spam": 0, "self_harm": 0, "policy_violation": 0,
}
_CLEAN_CATS = {k: 0 for k in _CAT_SCORES}
_RULES = [{"rule_id": "DIRECT_THREAT"}]


class TestTiebreak:
    def test_low_grade_returns_negative_modifier(self):
        with patch("services.llm_service._get_client", return_value=_make_client(
            {"grade": "LOW", "modifier": -0.25, "reasoning": "일상 과장 표현"}
        )):
            from services.tiebreaker import tiebreak
            modifier, reasoning = tiebreak("아 진짜 죽겠다", 0.45, _CAT_SCORES, [])
        assert modifier < 0
        assert reasoning == "일상 과장 표현"

    def test_high_grade_returns_positive_modifier(self):
        with patch("services.llm_service._get_client", return_value=_make_client(
            {"grade": "HIGH", "modifier": 0.25, "reasoning": "명백한 위협"}
        )):
            from services.tiebreaker import tiebreak
            modifier, reasoning = tiebreak("너 죽인다", 0.50, _CAT_SCORES, _RULES)
        assert modifier > 0
        assert reasoning == "명백한 위협"

    def test_medium_grade_returns_zero_modifier(self):
        with patch("services.llm_service._get_client", return_value=_make_client(
            {"grade": "MEDIUM", "modifier": 0.0, "reasoning": "불확실"}
        )):
            from services.tiebreaker import tiebreak
            modifier, _ = tiebreak("텍스트", 0.45, _CAT_SCORES, [])
        assert modifier == pytest.approx(0.0, abs=0.001)

    def test_modifier_clamped_to_negative_min(self):
        with patch("services.llm_service._get_client", return_value=_make_client(
            {"grade": "LOW", "modifier": -0.99, "reasoning": "극단적"}
        )):
            from services.tiebreaker import tiebreak
            modifier, _ = tiebreak("텍스트", 0.40, _CAT_SCORES, [])
        assert modifier == pytest.approx(-0.30, abs=0.001)

    def test_modifier_clamped_to_positive_max(self):
        with patch("services.llm_service._get_client", return_value=_make_client(
            {"grade": "HIGH", "modifier": 0.99, "reasoning": "극단적"}
        )):
            from services.tiebreaker import tiebreak
            modifier, _ = tiebreak("텍스트", 0.55, _CAT_SCORES, [])
        assert modifier == pytest.approx(0.30, abs=0.001)

    def test_llm_exception_returns_zero(self):
        mock_client = MagicMock()
        mock_client.chat.side_effect = ConnectionError("LLM 서버 오류")
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.tiebreaker import tiebreak
            modifier, reasoning = tiebreak("텍스트", 0.45, _CAT_SCORES, [])
        assert modifier == 0.0
        assert reasoning == ""

    def test_invalid_json_returns_zero(self):
        with patch("services.llm_service._get_client", return_value=_make_client("파싱 불가 텍스트")):
            from services.tiebreaker import tiebreak
            modifier, reasoning = tiebreak("텍스트", 0.45, _CAT_SCORES, [])
        assert modifier == 0.0
        assert reasoning == ""

    def test_missing_modifier_key_defaults_to_zero(self):
        with patch("services.llm_service._get_client", return_value=_make_client(
            {"grade": "HIGH", "reasoning": "modifier 키 없음"}
        )):
            from services.tiebreaker import tiebreak
            modifier, _ = tiebreak("텍스트", 0.45, _CAT_SCORES, [])
        assert modifier == 0.0

    def test_score_and_categories_appear_in_prompt(self):
        mock_client = _make_client({"grade": "MEDIUM", "modifier": 0.0, "reasoning": ""})
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.tiebreaker import tiebreak
            tiebreak("텍스트", 0.45, _CAT_SCORES, _RULES)
        called_prompt = mock_client.chat.call_args[0][1]
        assert "0.45" in called_prompt
        assert "profanity" in called_prompt

    def test_text_truncated_to_600_chars(self):
        long_text = "나" * 800
        mock_client = _make_client({"grade": "MEDIUM", "modifier": 0.0, "reasoning": ""})
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.tiebreaker import tiebreak
            tiebreak(long_text, 0.45, _CAT_SCORES, [])
        called_prompt = mock_client.chat.call_args[0][1]
        assert "나" * 601 not in called_prompt
