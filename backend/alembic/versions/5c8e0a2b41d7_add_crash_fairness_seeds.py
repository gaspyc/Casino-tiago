"""Guardar los seeds de cada ronda de Crash

Revision ID: 5c8e0a2b41d7
Revises: 4b7d9c1e2f30
Create Date: 2026-09-07 00:00:00.000000

Son nullable porque las rondas anteriores al provably fair no tienen seed: se
jugaron con `random.random()` y no hay nada que publicar de ellas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c8e0a2b41d7'
down_revision: Union[str, Sequence[str], None] = '4b7d9c1e2f30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('crash_game_sessions', sa.Column('server_seed', sa.String(), nullable=True))
    op.add_column('crash_game_sessions', sa.Column('server_seed_hash', sa.String(), nullable=True))
    op.add_column('crash_game_sessions', sa.Column('client_seed', sa.String(), nullable=True))
    op.add_column('crash_game_sessions', sa.Column('nonce', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('crash_game_sessions', 'nonce')
    op.drop_column('crash_game_sessions', 'client_seed')
    op.drop_column('crash_game_sessions', 'server_seed_hash')
    op.drop_column('crash_game_sessions', 'server_seed')
