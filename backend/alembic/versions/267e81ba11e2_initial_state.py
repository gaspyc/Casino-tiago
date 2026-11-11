"""Initial state

Revision ID: 267e81ba11e2
Revises:
Create Date: 2026-05-13 03:12:25.299936

Esta migración se autogeneró contra una base que ya tenía las tablas creadas por
`Base.metadata.create_all`, así que salió vacía y las tablas base nunca se creaban
en una base limpia. Acá quedan definidas. Cada create_table está guardado por un
chequeo de existencia para que también sea segura en bases que ya las tienen.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '267e81ba11e2'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    """Upgrade schema."""
    if not _has_table('users'):
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('username', sa.String(), nullable=False),
            sa.Column('email', sa.String(), nullable=False),
            sa.Column('hashed_password', sa.String(), nullable=False),
            sa.Column('balance', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
        op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    if not _has_table('transactions'):
        op.create_table(
            'transactions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('transaction_type', sa.String(), nullable=False),
            sa.Column('status', sa.String(), nullable=False, server_default='COMPLETED'),
            sa.Column('description', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_transactions_id'), 'transactions', ['id'], unique=False)

    if not _has_table('bets'):
        op.create_table(
            'bets',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('game_id', sa.String(), nullable=False),
            sa.Column('bet_amount', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('payout', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
            sa.Column('result_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_bets_id'), 'bets', ['id'], unique=False)

    if not _has_table('blackjack_games'):
        op.create_table(
            'blackjack_games',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('bet_amount', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('deck', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('player_hand', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('dealer_hand', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('status', sa.String(), nullable=False, server_default='ACTIVE'),
            sa.Column('is_split', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('active_hand_index', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_blackjack_games_id'), 'blackjack_games', ['id'], unique=False)

    if not _has_table('blackjack_tables'):
        op.create_table(
            'blackjack_tables',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('status', sa.String(), nullable=False, server_default='WAITING_PLAYERS'),
            sa.Column('deck', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('dealer_hand', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('players_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('current_turn_index', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_blackjack_tables_id'), 'blackjack_tables', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    for table in ('blackjack_tables', 'blackjack_games', 'bets', 'transactions', 'users'):
        if _has_table(table):
            op.drop_table(table)
