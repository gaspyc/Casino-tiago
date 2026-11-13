"""Generala contra la casa: pago por puntaje

Revision ID: e07a2d5b31c9
Revises: df60b1c4a872
Create Date: 2026-11-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e07a2d5b31c9'
down_revision: Union[str, Sequence[str], None] = 'e07c5a2b93f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Las partidas que ya existen se jugaron con pago binario y con la regla
    # de que la generala servida corta. Se marcan como tales: sus acciones
    # guardadas sólo rehacen la partida bajo esa regla, y si se las tratara
    # como nuevas dejarian de verificar.
    op.add_column(
        'generala_partidas',
        sa.Column('paga_por_puntaje', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
    )
    op.add_column('generala_partidas', sa.Column('puntaje', sa.Integer(), nullable=True))
    op.add_column(
        'generala_partidas',
        sa.Column('multiplicador', sa.Numeric(10, 4), nullable=True),
    )

    # De acá en adelante, lo que se crea paga por puntaje.
    op.alter_column('generala_partidas', 'paga_por_puntaje',
                    server_default=sa.text('true'))


def downgrade() -> None:
    op.drop_column('generala_partidas', 'multiplicador')
    op.drop_column('generala_partidas', 'puntaje')
    op.drop_column('generala_partidas', 'paga_por_puntaje')
