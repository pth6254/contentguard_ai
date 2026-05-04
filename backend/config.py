import os
import logging

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

    def validate(self) -> None:
        missing = [k for k, v in vars(self).items() if v == ""]
        # DATABASE_URL은 필수
        if not self.DATABASE_URL:
            raise RuntimeError("DATABASE_URL 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
        if missing:
            logger.warning("설정되지 않은 환경 변수: %s", missing)


settings = Settings()
settings.validate()
