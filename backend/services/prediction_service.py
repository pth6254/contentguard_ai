import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path

import joblib
import numpy as np

from config import settings
from services.decision_policy_service import classify_risk_level, get_recommended_action

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"

_BOUNDARIES = [0.30, 0.60, 0.85]

# Logistic Regression 클래스 레이블 → 연속 점수 변환 가중치 (각 등급 중간값)
_LEVEL_MIDPOINTS = {"LOW": 0.15, "MEDIUM": 0.44, "HIGH": 0.72, "CRITICAL": 0.92}


def _compute_confidence(risk_score: float) -> float:
    """결정 경계까지의 거리를 기반으로 신뢰도를 산출한다."""
    min_dist = min(abs(risk_score - b) for b in _BOUNDARIES)
    return round(min(1.0, min_dist / 0.15), 2)


class BaseMLModel(ABC):
    name: str
    version: str = "v1.0.0"
    model_type: str = "baseline"
    is_primary: bool = False

    @abstractmethod
    def predict(self, text: str) -> dict:
        """Return dict: risk_score, risk_level, recommended_action, confidence, latency_ms."""

    def as_metadata(self) -> dict:
        return {
            "model_name": self.name,
            "model_version": self.version,
            "model_type": self.model_type,
        }


class TfidfRidgeModel(BaseMLModel):
    name = "tfidf_ridge"
    version = "v1.0.0"
    model_type = "baseline"
    is_primary = False

    def __init__(self):
        try:
            self.vectorizer = joblib.load(MODELS_DIR / "tfidf_vectorizer.pkl")
            self.model = joblib.load(MODELS_DIR / "ridge_model.pkl")
            logger.info("TfidfRidgeModel 로드 완료")
        except FileNotFoundError:
            raise RuntimeError(
                "학습된 모델 파일이 없습니다. 먼저 'python scripts/train.py'를 실행하세요."
            )

    def predict(self, text: str) -> dict:
        t0 = time.perf_counter()
        X = self.vectorizer.transform([text])
        raw_score = float(self.model.predict(X)[0])
        risk_score = round(float(np.clip(raw_score, 0.0, 1.0)), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        risk_level = classify_risk_level(risk_score)
        recommended_action = get_recommended_action(risk_level)
        confidence = _compute_confidence(risk_score)

        logger.info(
            "TfidfRidge 예측 — score=%.2f level=%s latency=%dms",
            risk_score, risk_level, latency_ms,
        )

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "confidence": confidence,
            "latency_ms": latency_ms,
        }


class LinearSVMModel(BaseMLModel):
    """LinearSVR 기반 회귀 모델. Ridge와 동일한 연속 점수 방식."""

    name = "linear_svm"
    version = "v1.0.0"
    model_type = "linear_regressor"
    is_primary = False

    def __init__(self):
        try:
            self.vectorizer = joblib.load(MODELS_DIR / "tfidf_vectorizer.pkl")
            self.model = joblib.load(MODELS_DIR / "linear_svm_model.pkl")
            logger.info("LinearSVMModel 로드 완료")
        except FileNotFoundError as e:
            raise RuntimeError(
                f"linear_svm_model.pkl 없음 — 먼저 'python scripts/train.py'를 실행하세요. ({e})"
            )

    def predict(self, text: str) -> dict:
        t0 = time.perf_counter()
        X = self.vectorizer.transform([text])
        raw_score = float(self.model.predict(X)[0])
        risk_score = round(float(np.clip(raw_score, 0.0, 1.0)), 2)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        risk_level = classify_risk_level(risk_score)
        recommended_action = get_recommended_action(risk_level)
        confidence = _compute_confidence(risk_score)

        logger.info(
            "LinearSVM 예측 — score=%.2f level=%s latency=%dms",
            risk_score, risk_level, latency_ms,
        )

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "confidence": confidence,
            "latency_ms": latency_ms,
        }


class LogisticRegressionModel(BaseMLModel):
    """다중 클래스 분류 모델. 클래스 확률의 가중합으로 연속 점수를 산출한다."""

    name = "logistic_regression"
    version = "v1.0.0"
    model_type = "linear_classifier"
    is_primary = True

    def __init__(self):
        try:
            self.vectorizer = joblib.load(MODELS_DIR / "tfidf_vectorizer.pkl")
            self.model = joblib.load(MODELS_DIR / "logistic_regression_model.pkl")
            logger.info("LogisticRegressionModel 로드 완료")
        except FileNotFoundError as e:
            raise RuntimeError(
                f"logistic_regression_model.pkl 없음 — 먼저 'python scripts/train.py'를 실행하세요. ({e})"
            )

    def predict(self, text: str) -> dict:
        t0 = time.perf_counter()
        X = self.vectorizer.transform([text])
        proba = self.model.predict_proba(X)[0]
        classes = self.model.classes_          # 학습 시 결정된 클래스 순서
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # argmax 클래스의 범위 안에서 신뢰도에 따라 점수를 결정한다.
        # 가중평균 방식은 불확실할 때 MEDIUM으로 수렴하는 문제가 있어 이 방식을 사용.
        _RANGES = {"LOW": (0.00, 0.29), "MEDIUM": (0.30, 0.59), "HIGH": (0.60, 0.84), "CRITICAL": (0.85, 1.00)}
        pred_class = classes[int(np.argmax(proba))]
        confidence = round(float(proba.max()), 2)
        low, high = _RANGES[pred_class]
        risk_score = round(float(np.clip(low + (high - low) * confidence, 0.0, 1.0)), 2)

        risk_level = classify_risk_level(risk_score)
        recommended_action = get_recommended_action(risk_level)

        logger.info(
            "LogisticRegression 예측 — score=%.2f level=%s confidence=%.2f latency=%dms",
            risk_score, risk_level, confidence, latency_ms,
        )

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "confidence": confidence,
            "latency_ms": latency_ms,
        }


class ModelRegistry:
    """등록된 모든 ML 모델을 관리하고 예측을 조율한다."""

    def __init__(self):
        self._models: list[BaseMLModel] = []

    def register(self, model: BaseMLModel) -> None:
        self._models.append(model)
        logger.info("모델 등록: %s (%s)", model.name, model.version)

    def _primary_name(self) -> str:
        """MODEL_PRIMARY 환경변수 우선, 없으면 클래스 is_primary 폴백."""
        configured = settings.MODEL_PRIMARY
        if any(m.name == configured for m in self._models):
            return configured
        for m in self._models:
            if m.is_primary:
                return m.name
        return self._models[0].name

    @property
    def primary(self) -> BaseMLModel:
        name = self._primary_name()
        return next(m for m in self._models if m.name == name)

    def predict_all(self, text: str) -> list[dict]:
        """등록된 전체 모델을 실행하고 메타데이터·플래그를 포함한 결과 리스트를 반환한다."""
        primary_name = self._primary_name()
        results = []
        for model in self._models:
            result = model.predict(text)
            result.update(model.as_metadata())
            result["is_selected"] = model.name == primary_name
            result["is_shadow"] = not result["is_selected"]
            results.append(result)
        return results

    def get_final_result(self, predictions: list[dict]) -> dict:
        """DECISION_POLICY에 따라 복수 모델 예측을 최종 판단 하나로 합산한다."""
        policy = settings.DECISION_POLICY

        if policy == "conservative":
            # 전체 모델 중 가장 높은 위험 점수 채택
            best = max(predictions, key=lambda p: p["risk_score"])
            logger.info("Policy=conservative → %s (score=%.2f)", best["model_name"], best["risk_score"])
            return {k: best[k] for k in ("risk_score", "risk_level", "recommended_action")}

        if policy == "ensemble_mean":
            # 전체 모델 점수 평균
            mean_score = round(float(np.mean([p["risk_score"] for p in predictions])), 2)
            risk_level = classify_risk_level(mean_score)
            logger.info("Policy=ensemble_mean → score=%.2f level=%s", mean_score, risk_level)
            return {
                "risk_score": mean_score,
                "risk_level": risk_level,
                "recommended_action": get_recommended_action(risk_level),
            }

        if policy == "majority_vote":
            # 위험 등급 다수결 — 동률이면 더 높은 등급 우선
            levels = [p["risk_level"] for p in predictions]
            level_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            risk_level = max(
                set(levels),
                key=lambda l: (levels.count(l), level_order.index(l)),
            )
            matching = [p["risk_score"] for p in predictions if p["risk_level"] == risk_level]
            risk_score = round(float(np.mean(matching)), 2)
            logger.info("Policy=majority_vote → level=%s score=%.2f", risk_level, risk_score)
            return {
                "risk_score": risk_score,
                "risk_level": risk_level,
                "recommended_action": get_recommended_action(risk_level),
            }

        # primary_only (기본)
        primary = next(p for p in predictions if p["is_selected"])
        return {k: primary[k] for k in ("risk_score", "risk_level", "recommended_action")}


prediction_service = ModelRegistry()
prediction_service.register(TfidfRidgeModel())
prediction_service.register(LinearSVMModel())
prediction_service.register(LogisticRegressionModel())
