"""Partidas de truco contra la casa

Revision ID: 7e2a5b94c6f1
Revises: 6d1f3a9c7e24
Create Date: 2026-11-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '7e2a5b94c6f1'
down_revision: Union[str, Sequence[str], None] = '6d1f3a9c7e24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'truco_partidas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('apuesta', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('payout', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('server_seed', sa.String(), nullable=False),
        sa.Column('server_seed_hash', sa.String(), nullable=False),
        sa.Column('client_seed', sa.String(), nullable=False),
        sa.Column('nonce_base', sa.Integer(), nullable=False),
        sa.Column('acciones', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('terminada', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('ganador', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_truco_partidas_id'), 'truco_partidas', ['id'], unique=False)
    op.create_index(op.f('ix_truco_partidas_user_id'), 'truco_partidas', ['user_id'], unique=False)

    # Una sola partida abierta por jugador.
    op.create_index(
        'ix_truco_partida_abierta',
        'truco_partidas',
        ['user_id'],
        unique=True,
        postgresql_where=sa.text('terminada = false'),
    )


def downgrade() -> None:
    op.drop_index('ix_truco_partida_abierta', table_name='truco_partidas')
    op.drop_index(op.f('ix_truco_partidas_user_id'), table_name='truco_partidas')
    op.drop_index(op.f('ix_truco_partidas_id'), table_name='truco_partidas')
    op.drop_table('truco_partidas')
