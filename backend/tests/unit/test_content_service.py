import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch

from database import Base
from models import Content, ModelPrediction
from services.content_service import save_analysis


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


_PREDICTIONS = [
    {
        "model_name": "logistic_regression", "model_version": "v1.0.0", "model_type": "linear_classifier",
        "risk_score": 0.88, "risk_level": "CRITICAL", "recommended_action": "HOLD",
        "confidence": 0.92, "latency_ms": 3, "is_selected": True, "is_shadow": False,
    },
    {
        "model_name": "tfidf_ridge", "model_version": "v1.0.0", "model_type": "baseline",
        "risk_score": 0.75, "risk_level": "HIGH", "recommended_action": "REVIEW",
        "confidence": 0.80, "latency_ms": 5, "is_selected": False, "is_shadow": True,
    },
]

_FINAL = {"risk_score": 0.88, "risk_level": "CRITICAL", "recommended_action": "HOLD"}


class TestSaveAnalysisContent:
    def test_returns_content_record(self, db):
        record = save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL)
        assert isinstance(record, Content)

    def test_content_id_is_stored(self, db):
        record = save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL)
        assert record.content_id == "C001"

    def test_text_is_stored(self, db):
        record = save_analysis(db, "C001", "테스트 텍스트", None, _PREDICTIONS, _FINAL)
        assert record.text == "테스트 텍스트"

    def test_final_risk_fields_are_stored(self, db):
        record = save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL)
        assert record.risk_score == _FINAL["risk_score"]
        assert record.risk_level == _FINAL["risk_level"]
        assert record.recommended_action == _FINAL["recommended_action"]

    def test_client_id_is_stored(self, db):
        record = save_analysis(db, "C001", "테스트", 42, _PREDICTIONS, _FINAL)
        assert record.client_id == 42

    def test_client_id_none_when_not_provided(self, db):
        record = save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL)
        assert record.client_id is None

    def test_review_status_defaults_to_pending(self, db):
        record = save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL)
        assert record.review_status == "PENDING"


class TestSaveAnalysisExplanation:
    def test_explanation_stored_when_provided(self, db):
        record = save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL, explanation="설명입니다.")
        assert record.explanation == "설명입니다."

    def test_explanation_none_when_not_provided(self, db):
        record = save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL)
        assert record.explanation is None


class TestSaveAnalysisPredictions:
    def test_creates_one_prediction_per_model(self, db):
        save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL)
        preds = db.query(ModelPrediction).filter(ModelPrediction.content_id == "C001").all()
        assert len(preds) == len(_PREDICTIONS)

    def test_selected_flag_is_stored(self, db):
        save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL)
        preds = db.query(ModelPrediction).filter(ModelPrediction.content_id == "C001").all()
        selected = [p for p in preds if p.is_selected]
        assert len(selected) == 1
        assert selected[0].model_name == "logistic_regression"

    def test_shadow_flag_is_stored(self, db):
        save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL)
        preds = db.query(ModelPrediction).filter(ModelPrediction.content_id == "C001").all()
        shadow = [p for p in preds if p.is_shadow]
        assert len(shadow) == 1
        assert shadow[0].model_name == "tfidf_ridge"

    def test_prediction_scores_are_stored(self, db):
        save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL)
        preds = {p.model_name: p for p in db.query(ModelPrediction).filter(ModelPrediction.content_id == "C001")}
        assert preds["logistic_regression"].risk_score == 0.88
        assert preds["tfidf_ridge"].risk_score == 0.75


class TestSaveAnalysisTransaction:
    def test_rollback_on_db_error(self, db):
        broken_db = MagicMock()
        broken_db.add = MagicMock()
        broken_db.flush = MagicMock(side_effect=RuntimeError("DB 오류"))
        broken_db.rollback = MagicMock()

        with pytest.raises(RuntimeError, match="DB 오류"):
            save_analysis(broken_db, "C001", "테스트", None, _PREDICTIONS, _FINAL)

        broken_db.rollback.assert_called_once()

    def test_content_persisted_to_db(self, db):
        save_analysis(db, "C001", "테스트", None, _PREDICTIONS, _FINAL)
        assert db.query(Content).filter(Content.content_id == "C001").first() is not None
