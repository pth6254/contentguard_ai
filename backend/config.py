import os
import logging

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


VALID_POLICIES = {"primary_only", "conservative", "ensemble_mean", "majority_vote"}
VALID_LLM_PROVIDERS = {"ollama", "openai", "anthropic", "gemini", "deepseek"}


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

    # ── 텍스트 추출 전용 (크롤링 마크다운 → 사용자 텍스트 추출) ─────────────
    LLM_PROVIDER_EXTRACT: str = os.getenv("LLM_PROVIDER_EXTRACT", "")
    LLM_MODEL_EXTRACT: str = os.getenv("LLM_MODEL_EXTRACT", "")

    # ── 설명 생성 전용 (위험도 판단 근거 한국어 설명) ────────────────────────
    LLM_PROVIDER_EXPLAIN: str = os.getenv("LLM_PROVIDER_EXPLAIN", "")
    LLM_MODEL_EXPLAIN: str = os.getenv("LLM_MODEL_EXPLAIN", "")

    # 클라우드 LLM API 키
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    # Shadow Mode 설정 — 등록된 모델 이름 중 하나를 지정 (기본: logistic_regression)
    MODEL_PRIMARY: str = os.getenv("MODEL_PRIMARY", "logistic_regression")

    ALLOWED_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if o.strip()
    ]

    FIRECRAWL_API_KEY: str = os.getenv("FIRECRAWL_API_KEY", "")

    # 카테고리/모델 점수 조합 가중치 (합계 = 1.0 권장)
    SCORE_WEIGHT_MODEL: float = float(os.getenv("SCORE_WEIGHT_MODEL", "0.7"))
    SCORE_WEIGHT_CATEGORY: float = float(os.getenv("SCORE_WEIGHT_CATEGORY", "0.3"))

    # LLM 온도 — explain은 JSON 일관성을 위해 낮게, extract는 정밀 추출을 위해 낮게
    LLM_TEMPERATURE_EXPLAIN: float = float(os.getenv("LLM_TEMPERATURE_EXPLAIN", "0.1"))
    LLM_TEMPERATURE_EXTRACT: float = float(os.getenv("LLM_TEMPERATURE_EXTRACT", "0.1"))

    # LLM 맥락 검토 — true로 설정하면 LLM이 텍스트 의도를 평가해 점수를 최대 -0.30 조정
    # 레이턴시 +1~3초, LLM 호출 1회 추가. 기본 비활성.
    LLM_CONTEXT_REVIEW: bool = os.getenv("LLM_CONTEXT_REVIEW", "false").lower() == "true"
    ADMIN_SECRET: str = os.getenv("ADMIN_SECRET", "")

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24시간

    # 초기 운영자 시드 (operators 테이블이 비어 있으면 자동 생성)
    OPERATOR_EMAIL: str = os.getenv("OPERATOR_EMAIL", "")
    OPERATOR_PASSWORD: str = os.getenv("OPERATOR_PASSWORD", "")

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
        for key, val in [
            ("LLM_PROVIDER_EXTRACT", self.LLM_PROVIDER_EXTRACT),
            ("LLM_PROVIDER_EXPLAIN", self.LLM_PROVIDER_EXPLAIN),
        ]:
            if not val:
                raise RuntimeError(f"{key} 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
            if val not in VALID_LLM_PROVIDERS:
                raise RuntimeError(
                    f"{key}='{val}' 는 유효하지 않습니다. 허용값: {VALID_LLM_PROVIDERS}"
                )
        logger.info(
            "MODEL_PRIMARY=%s  DECISION_POLICY=%s  "
            "LLM extract=%s/%s  explain=%s/%s",
            self.MODEL_PRIMARY, self.DECISION_POLICY,
            self.LLM_PROVIDER_EXTRACT, self.LLM_MODEL_EXTRACT or "(default)",
            self.LLM_PROVIDER_EXPLAIN, self.LLM_MODEL_EXPLAIN or "(default)",
        )


settings = Settings()
settings.validate()
