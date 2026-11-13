"""Generala contra la casa

Revision ID: ce5b3f8a2049
Revises: bd4a2e7c9138
Create Date: 2026-11-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'ce5b3f8a2049'
down_revision: Union[str, Sequence[str], None] = 'bd4a2e7c9138'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'generala_partidas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('apuesta', sa.Numeric(10, 2), nullable=False),
        sa.Column('payout', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('server_seed', sa.String(), nullable=False),
        sa.Column('server_seed_hash', sa.String(), nullable=False),
        sa.Column('client_seed', sa.String(), nullable=False),
        sa.Column('nonce', sa.Integer(), nullable=False),
        sa.Column('empieza', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('acciones', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('terminada', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('ganador', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_generala_partidas_id'), 'generala_partidas', ['id'], unique=False)
    op.create_index(op.f('ix_generala_partidas_user_id'), 'generala_partidas', ['user_id'], unique=False)

    # Una sola partida abierta por jugador: dos serían dos apuestas debitadas.
    op.create_index(
        'ix_generala_partidas_abierta',
        'generala_partidas',
        ['user_id'],
        unique=True,
        postgresql_where=sa.text('NOT terminada'),
    )


def downgrade() -> None:
    op.drop_index('ix_generala_partidas_abierta', table_name='generala_partidas')
    op.drop_index(op.f('ix_generala_partidas_user_id'), table_name='generala_partidas')
    op.drop_index(op.f('ix_generala_partidas_id'), table_name='generala_partidas')
    op.drop_table('generala_partidas')
