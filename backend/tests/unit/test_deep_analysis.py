"""HIGH/CRITICAL 심층 분석 서비스 단위 테스트."""
import json
import pytest
from unittest.mock import MagicMock, patch


def _make_client(response: dict | str):
    mock_client = MagicMock()
    raw = response if isinstance(response, str) else json.dumps(response)
    mock_client.chat.return_value = raw
    return mock_client


_VALID_RESULT = {
    "is_targeted": True,
    "is_immediate": False,
    "actionability": "high",
    "target_description": "전 직장 동료",
    "suggested_action": "즉시 계정 정지 및 경찰 신고 검토",
}
_CAT_SCORES = {
    "profanity": 0, "threat": 95, "sexual": 0,
    "privacy": 0, "spam": 0, "self_harm": 0, "policy_violation": 0,
}
_RULES = [{"rule_id": "DIRECT_THREAT"}]
_SPANS = [
    {"text": "죽여버릴 거야", "category": "threat"},
    {"text": "집 알아냈어", "category": "privacy"},
]


class TestAnalyzeDeeply:
    def test_returns_dict_with_all_required_keys(self):
        with patch("services.llm_service._get_client", return_value=_make_client(_VALID_RESULT)):
            from services.deep_analysis import analyze_deeply
            result = analyze_deeply("죽여버릴 거야", "HIGH", _CAT_SCORES, _RULES, _SPANS)
        assert result is not None
        for key in ("is_targeted", "is_immediate", "actionability", "target_description", "suggested_action"):
            assert key in result

    def test_boolean_fields_are_bool_type(self):
        with patch("services.llm_service._get_client", return_value=_make_client(_VALID_RESULT)):
            from services.deep_analysis import analyze_deeply
            result = analyze_deeply("텍스트", "HIGH", _CAT_SCORES, _RULES, _SPANS)
        assert isinstance(result["is_targeted"], bool)
        assert isinstance(result["is_immediate"], bool)

    def test_bool_values_converted_from_llm(self):
        with patch("services.llm_service._get_client", return_value=_make_client(_VALID_RESULT)):
            from services.deep_analysis import analyze_deeply
            result = analyze_deeply("텍스트", "HIGH", _CAT_SCORES, _RULES, _SPANS)
        assert result["is_targeted"] is True
        assert result["is_immediate"] is False

    def test_actionability_field_preserved(self):
        with patch("services.llm_service._get_client", return_value=_make_client(_VALID_RESULT)):
            from services.deep_analysis import analyze_deeply
            result = analyze_deeply("텍스트", "CRITICAL", _CAT_SCORES, _RULES, _SPANS)
        assert result["actionability"] == "high"

    def test_string_fields_are_str_type(self):
        with patch("services.llm_service._get_client", return_value=_make_client(_VALID_RESULT)):
            from services.deep_analysis import analyze_deeply
            result = analyze_deeply("텍스트", "HIGH", _CAT_SCORES, _RULES, _SPANS)
        assert isinstance(result["target_description"], str)
        assert isinstance(result["suggested_action"], str)

    def test_llm_exception_returns_none(self):
        mock_client = MagicMock()
        mock_client.chat.side_effect = RuntimeError("타임아웃")
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.deep_analysis import analyze_deeply
            result = analyze_deeply("텍스트", "HIGH", _CAT_SCORES, _RULES, _SPANS)
        assert result is None

    def test_invalid_json_returns_none(self):
        with patch("services.llm_service._get_client", return_value=_make_client("파싱 불가")):
            from services.deep_analysis import analyze_deeply
            result = analyze_deeply("텍스트", "HIGH", _CAT_SCORES, _RULES, _SPANS)
        assert result is None

    def test_missing_fields_use_defaults(self):
        partial = {"is_targeted": True}
        with patch("services.llm_service._get_client", return_value=_make_client(partial)):
            from services.deep_analysis import analyze_deeply
            result = analyze_deeply("텍스트", "HIGH", _CAT_SCORES, _RULES, _SPANS)
        assert result is not None
        assert result["is_immediate"] is False
        assert result["actionability"] == "low"
        assert result["target_description"] == "불특정"
        assert result["suggested_action"] == ""

    def test_grade_appears_in_prompt(self):
        mock_client = _make_client(_VALID_RESULT)
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.deep_analysis import analyze_deeply
            analyze_deeply("텍스트", "CRITICAL", _CAT_SCORES, _RULES, _SPANS)
        called_prompt = mock_client.chat.call_args[0][1]
        assert "CRITICAL" in called_prompt

    def test_evidence_spans_limited_to_3_in_prompt(self):
        many_spans = [{"text": f"표현{i}", "category": "threat"} for i in range(10)]
        mock_client = _make_client(_VALID_RESULT)
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.deep_analysis import analyze_deeply
            analyze_deeply("텍스트", "HIGH", _CAT_SCORES, _RULES, many_spans)
        called_prompt = mock_client.chat.call_args[0][1]
        assert "표현3" not in called_prompt

    def test_empty_spans_uses_none_placeholder(self):
        mock_client = _make_client(_VALID_RESULT)
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.deep_analysis import analyze_deeply
            analyze_deeply("텍스트", "HIGH", _CAT_SCORES, [], [])
        called_prompt = mock_client.chat.call_args[0][1]
        assert "없음" in called_prompt

    def test_text_truncated_to_600_chars(self):
        long_text = "다" * 800
        mock_client = _make_client(_VALID_RESULT)
        with patch("services.llm_service._get_client", return_value=mock_client):
            from services.deep_analysis import analyze_deeply
            analyze_deeply(long_text, "HIGH", _CAT_SCORES, _RULES, _SPANS)
        called_prompt = mock_client.chat.call_args[0][1]
        assert "다" * 601 not in called_prompt
