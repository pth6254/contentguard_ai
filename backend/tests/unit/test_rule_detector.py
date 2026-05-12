"""PII 마스킹 + 강제 승격 규칙 단위 테스트."""
import pytest
from services.rule_detector import mask_pii, detect_rules, TriggeredRule


class TestMaskPii:
    def test_masks_korean_mobile_number(self):
        masked, detected = mask_pii("연락처는 010-1234-5678입니다")
        assert "[전화번호]" in masked
        assert "010-1234-5678" not in masked
        assert "전화번호" in detected

    def test_masks_email(self):
        masked, detected = mask_pii("이메일: user@example.com 로 문의하세요")
        assert "[이메일]" in masked
        assert "user@example.com" not in masked
        assert "이메일" in detected

    def test_masks_resident_number(self):
        masked, detected = mask_pii("주민번호 901010-1234567 확인")
        assert "[주민번호]" in masked
        assert "901010-1234567" not in masked
        assert "주민번호" in detected

    def test_masks_card_number(self):
        masked, detected = mask_pii("카드번호 1234-5678-9012-3456")
        assert "[카드번호]" in masked
        assert "1234-5678-9012-3456" not in masked
        assert "카드번호" in detected

    def test_clean_text_unchanged(self):
        text = "이 제품 진짜 좋아요"
        masked, detected = mask_pii(text)
        assert masked == text
        assert detected == []

    def test_multiple_pii_types_detected(self):
        text = "전화 010-1111-2222 이메일 a@b.com"
        masked, detected = mask_pii(text)
        assert len(detected) >= 2
        assert "010-1111-2222" not in masked
        assert "a@b.com" not in masked


class TestDetectRules:
    def test_pii_triggers_high_grade(self):
        rules = detect_rules("정상 텍스트", detected_pii=["전화번호"])
        rule_ids = [r.rule_id for r in rules]
        assert "PII_DETECTED" in rule_ids
        pii_rule = next(r for r in rules if r.rule_id == "PII_DETECTED")
        assert pii_rule.min_grade == "HIGH"

    def test_threat_triggers_high_grade(self):
        rules = detect_rules("너 죽여버릴 거야", detected_pii=[])
        rule_ids = [r.rule_id for r in rules]
        assert "DIRECT_THREAT" in rule_ids
        threat_rule = next(r for r in rules if r.rule_id == "DIRECT_THREAT")
        assert threat_rule.min_grade == "HIGH"
        assert threat_rule.category == "threat"

    def test_self_harm_triggers_critical(self):
        rules = detect_rules("더 이상 살고 싶지 않아 자살할 거야", detected_pii=[])
        rule_ids = [r.rule_id for r in rules]
        assert "SELF_HARM" in rule_ids
        sh_rule = next(r for r in rules if r.rule_id == "SELF_HARM")
        assert sh_rule.min_grade == "CRITICAL"

    def test_clean_text_triggers_no_rules(self):
        rules = detect_rules("오늘 날씨가 좋네요", detected_pii=[])
        assert rules == []

    def test_rule_to_dict_has_required_keys(self):
        rules = detect_rules("죽여버릴 거야", detected_pii=[])
        assert rules
        d = rules[0].to_dict()
        for key in ("rule_id", "description", "min_grade", "category", "matched_text"):
            assert key in d

    def test_multiple_rules_can_trigger(self):
        rules = detect_rules("죽여버릴 거야 죽고 싶다", detected_pii=["이메일"])
        rule_ids = {r.rule_id for r in rules}
        assert len(rule_ids) >= 2
