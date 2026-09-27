import os
import logging

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


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

    ALLOWED_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3003").split(",")
        if o.strip()
    ]

    FIRECRAWL_API_KEY: str = os.getenv("FIRECRAWL_API_KEY", "")

    # LLM 온도 — explain은 JSON 일관성을 위해 낮게, extract는 정밀 추출을 위해 낮게
    LLM_TEMPERATURE_EXPLAIN: float = float(os.getenv("LLM_TEMPERATURE_EXPLAIN", "0.1"))
    LLM_TEMPERATURE_EXTRACT: float = float(os.getenv("LLM_TEMPERATURE_EXTRACT", "0.1"))

    # LLM 최대 출력 토큰 수. Ollama는 기본 무제한이므로 명시적으로 제한해야 빠름.
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "800"))

    ADMIN_SECRET: str = os.getenv("ADMIN_SECRET", "")

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24시간

    # 초기 운영자 시드 (operators 테이블이 비어 있으면 자동 생성)
    OPERATOR_EMAIL: str = os.getenv("OPERATOR_EMAIL", "")
    OPERATOR_PASSWORD: str = os.getenv("OPERATOR_PASSWORD", "")

    # HIGH/CRITICAL LLM 심층 분석 — is_targeted, is_immediate, actionability 등 판단
    # HIGH/CRITICAL 케이스에서만 호출해 비용 부담을 제한. 기본 비활성.
    LLM_DEEP_ANALYSIS: bool = os.getenv("LLM_DEEP_ANALYSIS", "false").lower() == "true"

    def validate(self) -> None:
        if len(self.JWT_SECRET_KEY.encode("utf-8")) < 32 or self.JWT_SECRET_KEY.startswith("your-"):
            raise RuntimeError("JWT_SECRET_KEY에 무작위로 생성한 32바이트 이상의 비밀키를 설정하세요.")
        if self.JWT_EXPIRE_MINUTES <= 0:
            raise RuntimeError("JWT_EXPIRE_MINUTES는 양수여야 합니다.")
        if not self.DATABASE_URL:
            raise RuntimeError("DATABASE_URL 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
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
            "LLM extract=%s/%s  explain=%s/%s",
            self.LLM_PROVIDER_EXTRACT, self.LLM_MODEL_EXTRACT or "(default)",
            self.LLM_PROVIDER_EXPLAIN, self.LLM_MODEL_EXPLAIN or "(default)",
        )


settings = Settings()
settings.validate()
