"""Versioned customer-specific minimum-risk and review policies."""
import sqlalchemy as sa
from alembic import op

revision = "c8e31a0d42f7"
down_revision = "b47c12e5a901"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("client_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"), nullable=False, unique=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("category_min_levels", sa.JSON(), nullable=False),
        sa.Column("review_categories", sa.JSON(), nullable=False),
        sa.Column("trigger_score", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table("client_policies")
