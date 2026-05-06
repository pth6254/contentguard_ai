import os
import logging

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


VALID_POLICIES = {"primary_only", "conservative", "ensemble_mean", "majority_vote"}


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

    # Shadow Mode 설정 — 등록된 모델 이름 중 하나를 지정 (기본: logistic_regression)
    MODEL_PRIMARY: str = os.getenv("MODEL_PRIMARY", "logistic_regression")

    # Decision Policy — 복수 모델 결과를 최종 판단으로 합산하는 방식
    #   primary_only  : primary 모델 결과만 사용 (기본)
    #   conservative  : 전체 모델 중 가장 높은 위험 점수 채택
    #   ensemble_mean : 전체 모델 점수 평균
    #   majority_vote : 위험 등급 다수결
    DECISION_POLICY: str = os.getenv("DECISION_POLICY", "primary_only")

    def validate(self) -> None:
        if not self.DATABASE_URL:
            raise RuntimeError("DATABASE_URL 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
        if self.DECISION_POLICY not in VALID_POLICIES:
            raise RuntimeError(
                f"DECISION_POLICY='{self.DECISION_POLICY}' 는 유효하지 않습니다. "
                f"허용값: {VALID_POLICIES}"
            )
        logger.info("MODEL_PRIMARY=%s  DECISION_POLICY=%s", self.MODEL_PRIMARY, self.DECISION_POLICY)


settings = Settings()
settings.validate()
