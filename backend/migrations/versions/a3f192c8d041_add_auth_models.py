"""add auth models

Revision ID: a3f192c8d041
Revises: fcd865a7cc83
Create Date: 2026-05-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a3f192c8d041'
down_revision: Union[str, Sequence[str], None] = 'fcd865a7cc83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # clients 테이블에 email, password_hash 컬럼 추가
    op.add_column('clients', sa.Column('email', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('password_hash', sa.String(), nullable=True))
    op.create_index('ix_clients_email', 'clients', ['email'], unique=True)

    # operators 테이블 신규 생성 (id는 primary key이므로 별도 인덱스 불필요)
    op.create_table(
        'operators',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_operators_email', 'operators', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_operators_email', table_name='operators')
    op.drop_table('operators')
    op.drop_index('ix_clients_email', table_name='clients')
    op.drop_column('clients', 'password_hash')
    op.drop_column('clients', 'email')
