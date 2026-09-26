"""Add durable analysis jobs and review-after-reanalysis flag."""
import sqlalchemy as sa
from alembic import op

revision = "b47c12e5a901"
down_revision = "f6c20d9a7b41"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contents") as batch:
        batch.add_column(sa.Column("needs_re_review", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("analysis_jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id")),
        sa.Column("submission_key", sa.String(255), unique=True),
        sa.Column("content_id", sa.String(200), nullable=False),
        sa.Column("content_record_id", sa.Integer(), sa.ForeignKey("contents.id")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("pii_types", sa.JSON(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("last_error", sa.String(100)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime()))
    op.create_index("ix_analysis_jobs_client_id", "analysis_jobs", ["client_id"])
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"])
    op.create_index("ix_analysis_jobs_next_attempt_at", "analysis_jobs", ["next_attempt_at"])


def downgrade():
    op.drop_table("analysis_jobs")
    with op.batch_alter_table("contents") as batch:
        batch.drop_column("needs_re_review")
