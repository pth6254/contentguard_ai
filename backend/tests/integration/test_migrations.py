from pathlib import Path
import os
import uuid
import pytest

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema


@pytest.fixture(params=["sqlite", "postgresql"])
def migration_url(request, tmp_path):
    if request.param == "sqlite":
        yield f"sqlite:///{tmp_path / 'migration.db'}"
        return
    base_url = os.environ.get("TEST_DATABASE_URL", "")
    if not base_url.startswith("postgresql"):
        pytest.skip("Set TEST_DATABASE_URL to validate PostgreSQL migrations")
    schema = "migration_" + uuid.uuid4().hex
    engine = create_engine(base_url)
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        yield make_url(base_url).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def test_migration_preserves_existing_records_and_links(migration_url, monkeypatch):
    url = migration_url
    monkeypatch.setenv("DATABASE_URL", url)
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(config, "d4f7c9e2b851")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO clients(id,name,created_at) VALUES (1,'existing','2026-01-01')"))
        connection.execute(text("INSERT INTO contents(id,client_id,content_id,text,risk_score,risk_level,recommended_action,created_at) "
                                "VALUES (1,1,'old-id','preserved',0.1,'LOW','APPROVE','2026-01-01')"))
        connection.execute(text("INSERT INTO model_predictions(content_id,model_name,risk_score,risk_level,recommended_action) "
                                "VALUES ('old-id','old-model',0.1,'LOW','APPROVE')"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT text FROM contents WHERE id=1")).scalar() == "preserved"
        assert connection.execute(text("SELECT content_record_id FROM model_predictions")).scalar() == 1
        assert connection.execute(text("SELECT analysis_version FROM contents WHERE id=1")).scalar() == 1
        assert len(connection.execute(text("SELECT webhook_secret FROM clients WHERE id=1")).scalar()) == 64
        if engine.dialect.name == "sqlite":
            assert connection.execute(text("PRAGMA foreign_key_check")).fetchall() == []
    command.downgrade(config, "d4f7c9e2b851")
    command.upgrade(config, "head")
    engine.dispose()
