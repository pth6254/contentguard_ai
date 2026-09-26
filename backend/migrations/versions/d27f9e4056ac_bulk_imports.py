"""Track CSV/XLSX analysis batches and their durable jobs."""
import sqlalchemy as sa
from alembic import op

revision = "d27f9e4056ac"
down_revision = "c8e31a0d42f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("batch_imports",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id")),
        sa.Column("source_format", sa.String(8), nullable=False),
        sa.Column("rows_total", sa.Integer(), nullable=False),
        sa.Column("accepted", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_batch_imports_client_id", "batch_imports", ["client_id"])
    with op.batch_alter_table("analysis_jobs") as batch:
        batch.add_column(sa.Column("batch_id", sa.String(32), nullable=True))
        batch.create_foreign_key("fk_analysis_jobs_batch_id", "batch_imports", ["batch_id"], ["id"])
        batch.create_index("ix_analysis_jobs_batch_id", ["batch_id"])


def downgrade():
    with op.batch_alter_table("analysis_jobs") as batch:
        batch.drop_index("ix_analysis_jobs_batch_id")
        batch.drop_constraint("fk_analysis_jobs_batch_id", type_="foreignkey")
        batch.drop_column("batch_id")
    op.drop_table("batch_imports")
