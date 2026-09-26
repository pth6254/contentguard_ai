"""Persist analysis provenance and explicit evaluation labels."""
from datetime import datetime
import sqlalchemy as sa
from alembic import op

revision = "f6c20d9a7b41"
down_revision = "e91a2b4c630f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_record_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32)), sa.Column("model", sa.String(100)),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("category_scores", sa.JSON()), sa.Column("explanation_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_analysis_runs_content_record_id", "analysis_runs", ["content_record_id"])
    op.create_table("evaluation_labels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_record_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False, unique=True),
        sa.Column("expected_level", sa.String(16), nullable=False),
        sa.Column("category", sa.String(40)), sa.Column("reason", sa.Text()),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("operators.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_evaluation_labels_content_record_id", "evaluation_labels", ["content_record_id"])
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id,risk_score,risk_level,created_at,explanation_json,category_scores FROM contents")).fetchall()
    table = sa.table("analysis_runs", sa.column("content_record_id", sa.Integer()), sa.column("source", sa.String()),
                     sa.column("status", sa.String()), sa.column("risk_score", sa.Float()), sa.column("risk_level", sa.String()),
                     sa.column("provider", sa.String()), sa.column("model", sa.String()), sa.column("prompt_version", sa.String()),
                     sa.column("policy_version", sa.String()), sa.column("latency_ms", sa.Integer()),
                     sa.column("category_scores", sa.JSON()), sa.column("explanation_json", sa.JSON()),
                     sa.column("created_at", sa.DateTime()))
    import json
    for record_id, score, level, created, explanation, category_scores in rows:
        info = json.loads(explanation) if isinstance(explanation, str) else (explanation or {})
        if not isinstance(info, dict):
            info = {}
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        if isinstance(category_scores, str):
            category_scores = json.loads(category_scores)
        bind.execute(table.insert().values(content_record_id=record_id, source="legacy",
                     status=info.get("analysis_status", "legacy"), risk_score=score, risk_level=level,
                     provider=None, model=None, prompt_version="legacy", policy_version="legacy",
                     latency_ms=None, category_scores=category_scores, explanation_json=info,
                     created_at=created or datetime.utcnow()))


def downgrade():
    op.drop_table("evaluation_labels")
    op.drop_table("analysis_runs")
