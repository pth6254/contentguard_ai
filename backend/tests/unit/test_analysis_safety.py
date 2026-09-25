import json
from unittest.mock import Mock, patch

import pytest
from config import Settings
from services.analysis_service import analyze_text
from services.llm_service import classify_and_explain, _extract_with_llm, _CAT_NAMES
from services.rule_detector import mask_pii, detect_rules
from services.decision_policy_service import apply_forced_escalation
from services.deep_analysis import analyze_deeply


def classification(**updates):
    result = dict(risk_level="LOW", risk_score=0.1, category_scores={c: 0 for c in _CAT_NAMES},
                  summary="낮은 위험", score_explanation="근거", main_reasons=[], evidence=[],
                  recommended_operator_check="확인", confidence_note="")
    result.update(updates)
    return result


@pytest.mark.parametrize("secret", ["", "short", "your-secret-key-with-a-long-placeholder"])
def test_missing_or_placeholder_jwt_secret_fails_startup(secret):
    config = Settings()
    config.JWT_SECRET_KEY = secret
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        config.validate()


@pytest.mark.parametrize("response", [
    {"risk_level": "CRITICAL"}, classification(risk_level="CRITICAL"),
    classification(risk_score=float("nan")), classification(main_reasons="invalid"),
    classification(category_scores={"threat": 999}),
    classification(evidence=[{"quote": "없는 문구", "category": "threat", "why_it_matters": "위협"}]),
])
def test_bad_llm_output_is_explicit_fallback(response):
    with patch("services.llm_service._get_client", return_value=Mock(chat=Mock(return_value=json.dumps(response)))):
        result = analyze_text("평범한 문장")
    assert result["explanation_json"]["analysis_status"] == "fallback"
    assert result["final"]["recommended_action"] == "REVIEW"


def test_entire_text_sent_and_pii_masked():
    llm = Mock(chat=Mock(return_value=json.dumps(classification())))
    with patch("services.llm_service._get_client", return_value=llm):
        classify_and_explain("a" * 800 + "TAIL_MARKER 010-1234-5678", {c: 0 for c in _CAT_NAMES}, [])
    prompt = llm.chat.call_args.args[1]
    assert "TAIL_MARKER" in prompt
    assert "010-1234-5678" not in prompt


def test_stored_text_and_evidence_share_offsets():
    response = classification(risk_level="HIGH", risk_score=.8, category_scores={c: 90 if c == "threat" else 0 for c in _CAT_NAMES})
    with patch("services.analysis_service.classify_and_explain", return_value=response):
        result = analyze_text("😀 010-1234-5678 죽이겠다")
    assert "010-1234-5678" not in result["text"]
    assert result["evidence_spans"]
    for span in result["evidence_spans"]:
        assert result["text"][span["start_index"]:span["end_index"]] == span["text"]


@pytest.mark.parametrize("text", ["테러 예방 교육", '"죽고 싶다"는 친구를 돕는 방법', "https://example.com/login"])
def test_ambiguous_rules_require_review_without_forced_grade(text):
    _, pii = mask_pii(text)
    rules = detect_rules(text, pii)
    assert rules and all(r.review_only for r in rules)
    assert apply_forced_escalation(.1, rules)[1] == "LOW"
    with patch("services.analysis_service.classify_and_explain", return_value=classification()):
        result = analyze_text(text)
    assert result["final"]["recommended_action"] == "REVIEW"


def test_direct_threat_still_escalates_and_explains():
    with patch("services.analysis_service.classify_and_explain", return_value=classification()):
        result = analyze_text("너를 죽이겠다")
    assert result["final"]["risk_level"] == "HIGH"
    assert "HIGH" in result["explanation"]


@pytest.mark.parametrize("text,grade", [
    ("테러 예방 교육. 하지만 너를 죽이겠다", "HIGH"),
    ('"죽고 싶다"는 친구를 돕는 방법. 나는 지금 자살할 거야', "CRITICAL"),
])
def test_reported_prefix_does_not_hide_later_direct_threat(text, grade):
    with patch("services.analysis_service.classify_and_explain", return_value=classification()):
        result = analyze_text(text)
    assert result["final"]["risk_level"] == grade


def test_deep_analysis_masks_pii_and_rejects_string_boolean():
    llm = Mock(chat=Mock(return_value=json.dumps(dict(is_targeted="false", is_immediate=False,
                actionability="low", target_description="", suggested_action=""))))
    with patch("services.llm_service._get_client", return_value=llm):
        assert analyze_deeply("010-1234-5678", "HIGH", {}, [], []) is None
    assert "010-1234-5678" not in llm.chat.call_args.args[1]


def test_extraction_masks_pii_and_limits_results():
    llm = Mock(chat=Mock(return_value=json.dumps(["첫째", "둘째", "셋째"])))
    with patch("services.llm_service._get_client", return_value=llm):
        assert len(_extract_with_llm("email: user@example.com", 2)) == 2
    assert "user@example.com" not in llm.chat.call_args.args[1]
