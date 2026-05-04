import logging
from pathlib import Path

import joblib
import numpy as np

from services.risk_service import classify_risk_level, get_recommended_action

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"


class PredictionService:
    def __init__(self):
        self.vectorizer = None
        self.model = None
        self._load_models()

    def _load_models(self):
        try:
            self.vectorizer = joblib.load(MODELS_DIR / "tfidf_vectorizer.pkl")
            self.model = joblib.load(MODELS_DIR / "ridge_model.pkl")
            logger.info("ML 모델 로드 완료")
        except FileNotFoundError:
            raise RuntimeError(
                "학습된 모델 파일이 없습니다. 먼저 'python scripts/train.py'를 실행하세요."
            )

    def predict(self, text: str) -> dict:
        X = self.vectorizer.transform([text])

        raw_score = float(self.model.predict(X)[0])
        risk_score = round(float(np.clip(raw_score, 0.0, 1.0)), 2)

        risk_level = classify_risk_level(risk_score)
        recommended_action = get_recommended_action(risk_level)

        logger.info(
            "예측 완료 — score=%.2f level=%s action=%s",
            risk_score,
            risk_level,
            recommended_action,
        )

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "recommended_action": recommended_action,
        }


prediction_service = PredictionService()
