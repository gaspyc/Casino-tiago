"""Plazo de turno en las mesas de truco

Sin plazo, el que va perdiendo nunca está obligado a perder: le alcanza con
dejar de jugar, porque el rival sólo puede abandonar —y abandonar es entregar
la mesa. `ultima_accion` es contra qué se mide el plazo y `motivo` distingue
cómo terminó cada mesa.

Revision ID: e07c5a2b93f4
Revises: df60b1c4a872
Create Date: 2026-11-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e07c5a2b93f4'
down_revision: Union[str, Sequence[str], None] = 'df60b1c4a872'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'truco_mesas',
        sa.Column('motivo', sa.String(), nullable=True),
    )
    # Las mesas que ya estaban abiertas arrancan el plazo desde ahora: medirlo
    # contra su created_at las dejaría vencidas de entrada y reclamables al
    # instante, sin que nadie hubiera tenido chance de jugar.
    op.add_column(
        'truco_mesas',
        sa.Column(
            'ultima_accion',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('truco_mesas', 'ultima_accion')
    op.drop_column('truco_mesas', 'motivo')
