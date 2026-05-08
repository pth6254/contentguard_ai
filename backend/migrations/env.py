import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# backend/ 디렉토리를 sys.path에 추가해 모듈 임포트 가능하게 함
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base
import models  # noqa: F401 — 모든 모델이 Base.metadata에 등록되도록 임포트

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# .env의 DATABASE_URL을 alembic.ini보다 우선 적용
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
