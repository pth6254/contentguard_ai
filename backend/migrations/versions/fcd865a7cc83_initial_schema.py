"""initial schema

Revision ID: fcd865a7cc83
Revises:
Create Date: 2026-05-08 10:26:29.208752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fcd865a7cc83'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('key_prefix', sa.String(16), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'contents',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('client_id', sa.Integer(), sa.ForeignKey('clients.id'), nullable=True, index=True),
        sa.Column('content_id', sa.String(), nullable=False, unique=True, index=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('risk_level', sa.String(), nullable=False),
        sa.Column('recommended_action', sa.String(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('review_status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('review_action', sa.String(), nullable=True),
        sa.Column('reviewer_comment', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'model_predictions',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('content_id', sa.String(), sa.ForeignKey('contents.content_id'), nullable=False, index=True),
        sa.Column('model_name', sa.String(), nullable=False, index=True),
        sa.Column('model_version', sa.String(), nullable=False, server_default='v1.0.0'),
        sa.Column('model_type', sa.String(), nullable=False, server_default='baseline'),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('risk_level', sa.String(), nullable=False),
        sa.Column('recommended_action', sa.String(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('is_selected', sa.Boolean(), server_default='false'),
        sa.Column('is_shadow', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table('model_predictions')
    op.drop_table('contents')
    op.drop_table('api_keys')
    op.drop_table('clients')
