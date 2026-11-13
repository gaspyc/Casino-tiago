"""Compromiso provably fair en las manos de blackjack

Revision ID: ac3f9d1e5b27
Revises: 9b5e2c8a4d16
Create Date: 2026-11-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ac3f9d1e5b27'
down_revision: Union[str, Sequence[str], None] = '9b5e2c8a4d16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: las manos ya jugadas no tienen compromiso y no se pueden
    # inventar, así que quedan marcadas como no verificables.
    op.add_column('blackjack_games', sa.Column('seed_id', sa.Integer(), nullable=True))
    op.add_column('blackjack_games', sa.Column('nonce', sa.Integer(), nullable=True))
    op.add_column('blackjack_games', sa.Column('server_seed_hash', sa.String(), nullable=True))
    op.add_column('blackjack_games', sa.Column('client_seed', sa.String(), nullable=True))

    op.create_foreign_key(
        'fk_blackjack_games_seed_id',
        'blackjack_games',
        'game_seeds',
        ['seed_id'],
        ['id'],
    )
    op.create_index(
        'ix_blackjack_games_seed_id', 'blackjack_games', ['seed_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_blackjack_games_seed_id', table_name='blackjack_games')
    op.drop_constraint('fk_blackjack_games_seed_id', 'blackjack_games', type_='foreignkey')
    op.drop_column('blackjack_games', 'client_seed')
    op.drop_column('blackjack_games', 'server_seed_hash')
    op.drop_column('blackjack_games', 'nonce')
    op.drop_column('blackjack_games', 'seed_id')
