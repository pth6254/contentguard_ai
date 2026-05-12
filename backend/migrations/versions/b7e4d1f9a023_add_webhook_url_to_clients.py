"""add webhook_url to clients

Revision ID: b7e4d1f9a023
Revises: a3f192c8d041
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b7e4d1f9a023'
down_revision: Union[str, Sequence[str], None] = 'a3f192c8d041'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clients', sa.Column('webhook_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('clients', 'webhook_url')
