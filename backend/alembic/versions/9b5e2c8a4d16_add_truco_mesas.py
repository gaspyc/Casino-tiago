"""Mesas de truco entre jugadores

Revision ID: 9b5e2c8a4d16
Revises: 8a4c1d7f2b35
Create Date: 2026-11-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '9b5e2c8a4d16'
down_revision: Union[str, Sequence[str], None] = '8a4c1d7f2b35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'truco_mesas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jugador_0_id', sa.Integer(), nullable=False),
        sa.Column('jugador_1_id', sa.Integer(), nullable=True),
        sa.Column('apuesta', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('con_flor', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('estado', sa.String(), nullable=False, server_default='esperando'),
        sa.Column('server_seed', sa.String(), nullable=False),
        sa.Column('server_seed_hash', sa.String(), nullable=False),
        sa.Column('client_seed', sa.String(), nullable=False),
        sa.Column('nonce_base', sa.Integer(), nullable=False),
        sa.Column('acciones', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('ganador', sa.Integer(), nullable=True),
        sa.Column('premio', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('comision', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['jugador_0_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['jugador_1_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_truco_mesas_id'), 'truco_mesas', ['id'], unique=False)
    op.create_index(op.f('ix_truco_mesas_jugador_0_id'), 'truco_mesas', ['jugador_0_id'], unique=False)
    op.create_index(op.f('ix_truco_mesas_jugador_1_id'), 'truco_mesas', ['jugador_1_id'], unique=False)
    op.create_index('ix_truco_mesas_estado', 'truco_mesas', ['estado'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_truco_mesas_estado', table_name='truco_mesas')
    op.drop_index(op.f('ix_truco_mesas_jugador_1_id'), table_name='truco_mesas')
    op.drop_index(op.f('ix_truco_mesas_jugador_0_id'), table_name='truco_mesas')
    op.drop_index(op.f('ix_truco_mesas_id'), table_name='truco_mesas')
    op.drop_table('truco_mesas')
