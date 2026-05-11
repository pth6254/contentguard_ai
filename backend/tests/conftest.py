# Must set env vars before any backend module is imported
import os
from pathlib import Path

_TEST_DB_PATH = Path(__file__).parent / "test_contentguard.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ.setdefault("MODEL_PRIMARY", "logistic_regression")
os.environ.setdefault("DECISION_POLICY", "primary_only")
os.environ.setdefault("ADMIN_SECRET", "test-secret")
os.environ["TESTING"] = "true"

OPERATOR_SECRET = os.environ["ADMIN_SECRET"]

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from database import Base, get_db
from main import app
from models import Client
from auth import get_client, get_client_or_operator, require_operator
from services.prediction_service import prediction_service

_test_engine = create_engine(
    f"sqlite:///{_TEST_DB_PATH}",
    connect_args={"check_same_thread": False},
)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

MOCK_PREDICTIONS = [
    {
        "model_name": "tfidf_ridge",
        "model_version": "v1.0.0",
        "model_type": "baseline",
        "risk_score": 0.75,
        "risk_level": "HIGH",
        "recommended_action": "REVIEW",
        "confidence": 0.80,
        "latency_ms": 5,
        "is_selected": False,
        "is_shadow": True,
    },
    {
        "model_name": "linear_svm",
        "model_version": "v1.0.0",
        "model_type": "linear_regressor",
        "risk_score": 0.70,
        "risk_level": "HIGH",
        "recommended_action": "REVIEW",
        "confidence": 0.75,
        "latency_ms": 4,
        "is_selected": False,
        "is_shadow": True,
    },
    {
        "model_name": "logistic_regression",
        "model_version": "v1.0.0",
        "model_type": "linear_classifier",
        "risk_score": 0.88,
        "risk_level": "CRITICAL",
        "recommended_action": "HOLD",
        "confidence": 0.92,
        "latency_ms": 3,
        "is_selected": True,
        "is_shadow": False,
    },
]

MOCK_FINAL_RESULT = {
    "risk_score": 0.88,
    "risk_level": "CRITICAL",
    "recommended_action": "HOLD",
}


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=_test_engine)
    session = _TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_test_engine)


_MOCK_CLIENT = Client(id=1, name="test-client")


@pytest.fixture(scope="function")
def unauth_client(db_session):
    """get_client / require_operator를 override하지 않는 클라이언트 (인증 강제 확인용)."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session

    def override_get_client():
        return _MOCK_CLIENT

    def override_get_client_or_operator():
        return _MOCK_CLIENT

    def override_require_operator():
        return None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_client] = override_get_client
    app.dependency_overrides[get_client_or_operator] = override_get_client_or_operator
    app.dependency_overrides[require_operator] = override_require_operator
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture
def mock_predict():
    with (
        patch.object(prediction_service, "predict_all", return_value=MOCK_PREDICTIONS),
        patch.object(prediction_service, "get_final_result", return_value=MOCK_FINAL_RESULT),
        patch("routers.analyze.generate_explanation", return_value="테스트 설명입니다."),
        patch("routers.upload.generate_explanation", return_value="테스트 설명입니다."),
        patch("routers.crawl.generate_explanation", return_value="테스트 설명입니다."),
    ):
        yield


@pytest.fixture
def analyzed_content(client, mock_predict):
    """Analyze API를 호출해 콘텐츠 레코드를 생성하고 응답 dict를 반환한다."""
    response = client.post(
        "/api/analyze",
        json={"content_id": "TEST001", "text": "테스트 콘텐츠입니다"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    try:
        _TEST_DB_PATH.unlink(missing_ok=True)
    except Exception:
        pass
