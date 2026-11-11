"""Semillas provably fair por jugador

Revision ID: 6d1f3a9c7e24
Revises: 5c8e0a2b41d7
Create Date: 2026-11-11 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d1f3a9c7e24'
down_revision: Union[str, Sequence[str], None] = '5c8e0a2b41d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'game_seeds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.String(), nullable=False),
        sa.Column('server_seed', sa.String(), nullable=False),
        sa.Column('server_seed_hash', sa.String(), nullable=False),
        sa.Column('client_seed', sa.String(), nullable=False),
        sa.Column('nonce', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('revealed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_game_seeds_id'), 'game_seeds', ['id'], unique=False)
    op.create_index(op.f('ix_game_seeds_user_id'), 'game_seeds', ['user_id'], unique=False)

    # Una sola semilla activa por jugador y juego.
    op.create_index(
        'ix_game_seeds_activa',
        'game_seeds',
        ['user_id', 'game_id'],
        unique=True,
        postgresql_where=sa.text('revealed_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_game_seeds_activa', table_name='game_seeds')
    op.drop_index(op.f('ix_game_seeds_user_id'), table_name='game_seeds')
    op.drop_index(op.f('ix_game_seeds_id'), table_name='game_seeds')
    op.drop_table('game_seeds')
