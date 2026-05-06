import pytest
from datetime import datetime
from pydantic import ValidationError

from schemas import AnalyzeRequest, ContentResponse, ReviewRequest


class TestAnalyzeRequest:
    def test_valid_request(self):
        req = AnalyzeRequest(content_id="C001", text="테스트 텍스트")
        assert req.content_id == "C001"
        assert req.text == "테스트 텍스트"

    def test_empty_text_rejected(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(content_id="C001", text="")

    def test_missing_content_id_rejected(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(text="텍스트")

    def test_missing_text_rejected(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(content_id="C001")

    def test_whitespace_only_text_accepted(self):
        # min_length=1 이므로 공백 1자는 통과
        req = AnalyzeRequest(content_id="C001", text=" ")
        assert req.text == " "


class TestReviewRequest:
    @pytest.mark.parametrize("action", ["approve", "remove", "hold", "monitor"])
    def test_all_valid_actions(self, action):
        req = ReviewRequest(action=action)
        assert req.action == action

    def test_invalid_action_rejected(self):
        with pytest.raises(ValidationError):
            ReviewRequest(action="ban")

    def test_invalid_action_uppercase_rejected(self):
        with pytest.raises(ValidationError):
            ReviewRequest(action="APPROVE")

    def test_comment_optional(self):
        req = ReviewRequest(action="approve")
        assert req.comment is None

    def test_comment_stored(self):
        req = ReviewRequest(action="hold", comment="추가 검토 필요")
        assert req.comment == "추가 검토 필요"

    def test_missing_action_rejected(self):
        with pytest.raises(ValidationError):
            ReviewRequest()


class TestContentResponse:
    def _base_data(self):
        return {
            "content_id": "C001",
            "text": "테스트 콘텐츠",
            "risk_score": 0.75,
            "risk_level": "HIGH",
            "recommended_action": "REVIEW",
            "review_status": "PENDING",
            "created_at": datetime.utcnow(),
        }

    def test_valid_minimal_response(self):
        resp = ContentResponse(**self._base_data())
        assert resp.content_id == "C001"
        assert resp.risk_score == 0.75

    def test_optional_fields_default_to_none(self):
        resp = ContentResponse(**self._base_data())
        assert resp.explanation is None
        assert resp.review_action is None
        assert resp.reviewer_comment is None
        assert resp.reviewed_at is None

    def test_with_all_optional_fields(self):
        data = self._base_data()
        data.update({
            "explanation": "AI 생성 설명",
            "review_action": "approve",
            "reviewer_comment": "문제없음",
            "reviewed_at": datetime.utcnow(),
        })
        resp = ContentResponse(**data)
        assert resp.explanation == "AI 생성 설명"
        assert resp.review_action == "approve"
