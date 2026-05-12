"""add analysis detail columns (category_scores, triggered_rules, evidence_spans, explanation_json, calibrated_score)

Revision ID: d4f7c9e2b851
Revises: b7e4d1f9a023
Create Date: 2026-05-12 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4f7c9e2b851'
down_revision: Union[str, Sequence[str], None] = 'b7e4d1f9a023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_type():
    """PostgreSQL은 JSONB, 그 외 방언은 JSON을 사용한다."""
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import JSONB
        return JSONB
    return sa.JSON


def upgrade() -> None:
    jt = _json_type()
    op.add_column('contents', sa.Column('raw_model_score',  sa.Float(),  nullable=True))
    op.add_column('contents', sa.Column('calibrated_score', sa.Float(),  nullable=True))
    op.add_column('contents', sa.Column('category_scores',  jt(),        nullable=True))
    op.add_column('contents', sa.Column('triggered_rules',  jt(),        nullable=True))
    op.add_column('contents', sa.Column('evidence_spans',   jt(),        nullable=True))
    op.add_column('contents', sa.Column('explanation_json', jt(),        nullable=True))


def downgrade() -> None:
    op.drop_column('contents', 'explanation_json')
    op.drop_column('contents', 'evidence_spans')
    op.drop_column('contents', 'triggered_rules')
    op.drop_column('contents', 'category_scores')
    op.drop_column('contents', 'calibrated_score')
    op.drop_column('contents', 'raw_model_score')
