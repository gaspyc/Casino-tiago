"""Mines

Revision ID: bd4a2e7c9138
Revises: ac3f9d1e5b27
Create Date: 2026-11-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'bd4a2e7c9138'
down_revision: Union[str, Sequence[str], None] = 'ac3f9d1e5b27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mines_games',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('bet_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('minas', sa.Integer(), nullable=False),
        sa.Column('destapadas', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
        sa.Column('payout', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('seed_id', sa.Integer(), nullable=False),
        sa.Column('nonce', sa.Integer(), nullable=False),
        sa.Column('server_seed_hash', sa.String(), nullable=False),
        sa.Column('client_seed', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.CheckConstraint('minas >= 1 AND minas <= 24', name='ck_mines_games_minas'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['seed_id'], ['game_seeds.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_mines_games_id'), 'mines_games', ['id'], unique=False)
    op.create_index(op.f('ix_mines_games_user_id'), 'mines_games', ['user_id'], unique=False)

    # Una sola grilla abierta por jugador: el resto del servicio lo da por
    # sentado, y una segunda grilla abierta dejaría plata debitada sin dueño.
    op.create_index(
        'ix_mines_games_activa',
        'mines_games',
        ['user_id'],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index('ix_mines_games_activa', table_name='mines_games')
    op.drop_index(op.f('ix_mines_games_user_id'), table_name='mines_games')
    op.drop_index(op.f('ix_mines_games_id'), table_name='mines_games')
    op.drop_table('mines_games')
