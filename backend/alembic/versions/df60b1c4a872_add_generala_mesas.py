"""Mesas de generala entre dos jugadores

Revision ID: df60b1c4a872
Revises: ce5b3f8a2049
Create Date: 2026-11-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'df60b1c4a872'
down_revision: Union[str, Sequence[str], None] = 'ce5b3f8a2049'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'generala_mesas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jugador_0_id', sa.Integer(), nullable=False),
        sa.Column('jugador_1_id', sa.Integer(), nullable=True),
        sa.Column('apuesta', sa.Numeric(10, 2), nullable=False),
        sa.Column('estado', sa.String(), nullable=False, server_default='esperando'),
        sa.Column('server_seed', sa.String(), nullable=False),
        sa.Column('server_seed_hash', sa.String(), nullable=False),
        sa.Column('client_seed', sa.String(), nullable=False),
        sa.Column('nonce', sa.Integer(), nullable=False),
        sa.Column('empieza', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('acciones', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('ganador', sa.Integer(), nullable=True),
        sa.Column('premio', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('comision', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('motivo', sa.String(), nullable=True),
        sa.Column('ultima_accion', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['jugador_0_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['jugador_1_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_generala_mesas_id'), 'generala_mesas', ['id'], unique=False)
    op.create_index(op.f('ix_generala_mesas_jugador_0_id'), 'generala_mesas', ['jugador_0_id'], unique=False)
    op.create_index(op.f('ix_generala_mesas_jugador_1_id'), 'generala_mesas', ['jugador_1_id'], unique=False)
    op.create_index('ix_generala_mesas_estado', 'generala_mesas', ['estado'], unique=False)

    # Una sola mesa sin terminar por jugador, en cualquiera de los dos
    # asientos. El chequeo de la aplicación ya lo cubre en el caso normal;
    # esto es lo que cierra la carrera de dos pedidos simultáneos, que sin el
    # índice debitaría dos apuestas.
    op.create_index(
        'ix_generala_mesas_asiento_0_abierta',
        'generala_mesas',
        ['jugador_0_id'],
        unique=True,
        postgresql_where=sa.text("estado <> 'terminada'"),
    )
    op.create_index(
        'ix_generala_mesas_asiento_1_abierta',
        'generala_mesas',
        ['jugador_1_id'],
        unique=True,
        postgresql_where=sa.text("estado <> 'terminada' AND jugador_1_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index('ix_generala_mesas_asiento_1_abierta', table_name='generala_mesas')
    op.drop_index('ix_generala_mesas_asiento_0_abierta', table_name='generala_mesas')
    op.drop_index('ix_generala_mesas_estado', table_name='generala_mesas')
    op.drop_index(op.f('ix_generala_mesas_jugador_1_id'), table_name='generala_mesas')
    op.drop_index(op.f('ix_generala_mesas_jugador_0_id'), table_name='generala_mesas')
    op.drop_index(op.f('ix_generala_mesas_id'), table_name='generala_mesas')
    op.drop_table('generala_mesas')
