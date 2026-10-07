"""Analysis version checks, worker leases, frozen evaluations, batch errors.

Revision ID: e50a61c972bd
Revises: d27f9e4056ac
"""
from alembic import op
import sqlalchemy as sa

revision = "e50a61c972bd"
down_revision = "d27f9e4056ac"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("contents", sa.Column("analysis_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("analysis_runs", sa.Column("analysis_version", sa.Integer(), nullable=False, server_default="0"))
    op.execute("UPDATE analysis_runs SET analysis_version = (SELECT count(*) FROM analysis_runs r WHERE r.content_record_id = analysis_runs.content_record_id AND r.id <= analysis_runs.id)")
    op.execute("UPDATE contents SET analysis_version = (SELECT count(*) FROM analysis_runs r WHERE r.content_record_id = contents.id)")
    op.execute("UPDATE contents SET analysis_version = 1 WHERE analysis_version = 0")
    op.add_column("review_events", sa.Column("analysis_version", sa.Integer(), nullable=True))
    op.add_column("analysis_jobs", sa.Column("lease_token", sa.String(32), nullable=True))
    op.add_column("batch_imports", sa.Column("errors", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.create_table("worker_heartbeats", sa.Column("id", sa.String(32), primary_key=True),
                    sa.Column("kind", sa.String(16), nullable=False), sa.Column("last_seen_at", sa.DateTime(), nullable=False))
    op.create_index("ix_worker_heartbeats_kind", "worker_heartbeats", ["kind"])
    op.create_table("evaluation_datasets", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("name", sa.String(100), nullable=False), sa.Column("items", sa.JSON(), nullable=False),
                    sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_table("evaluation_reports", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("evaluation_datasets.id"), nullable=False),
                    sa.Column("name", sa.String(100), nullable=False), sa.Column("filters", sa.JSON(), nullable=False),
                    sa.Column("run_ids", sa.JSON(), nullable=False), sa.Column("metrics", sa.JSON(), nullable=False),
                    sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_evaluation_reports_dataset_id", "evaluation_reports", ["dataset_id"])


def downgrade():
    op.drop_table("evaluation_reports")
    op.drop_table("evaluation_datasets")
    op.drop_table("worker_heartbeats")
    with op.batch_alter_table("batch_imports") as batch:
        batch.drop_column("errors")
    with op.batch_alter_table("analysis_jobs") as batch:
        batch.drop_column("lease_token")
    with op.batch_alter_table("review_events") as batch:
        batch.drop_column("analysis_version")
    with op.batch_alter_table("analysis_runs") as batch:
        batch.drop_column("analysis_version")
    with op.batch_alter_table("contents") as batch:
        batch.drop_column("analysis_version")
