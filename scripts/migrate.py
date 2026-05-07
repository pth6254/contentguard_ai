"""
DB 스키마 마이그레이션 스크립트
실행: python scripts/migrate.py  (contentguard_ai/ 루트에서)

새로 추가된 테이블/컬럼:
  - clients 테이블 (신규)
  - api_keys 테이블 (신규)
  - contents.client_id 컬럼 (기존 테이블에 추가)
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from database import engine, Base
from models import Client, ApiKey, Content, ModelPrediction  # noqa: F401 — 테이블 등록용


def migrate():
    # 1. 신규 테이블 생성 (clients, api_keys)
    Base.metadata.create_all(bind=engine)
    print("신규 테이블 생성 완료 (clients, api_keys)")

    # 2. contents 테이블에 client_id 컬럼 추가 (이미 있으면 무시)
    with engine.connect() as conn:
        from sqlalchemy import text
        try:
            conn.execute(text(
                "ALTER TABLE contents ADD COLUMN client_id INTEGER REFERENCES clients(id)"
            ))
            conn.commit()
            print("contents.client_id 컬럼 추가 완료")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("contents.client_id 컬럼 이미 존재 — 건너뜀")
            else:
                print(f"마이그레이션 오류: {e}")
                raise

    print("\n마이그레이션 완료")


if __name__ == "__main__":
    migrate()
