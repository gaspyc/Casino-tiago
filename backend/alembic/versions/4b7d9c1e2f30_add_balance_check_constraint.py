"""Impedir saldos negativos a nivel de base

Revision ID: 4b7d9c1e2f30
Revises: 3a2c4e5b6d7f
Create Date: 2026-09-07 00:00:00.000000

Última red de contención del débito atómico: aunque un servicio nuevo se olvide
de usar `debit()`, la base rechaza dejar un saldo por debajo de cero.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b7d9c1e2f30'
down_revision: Union[str, Sequence[str], None] = '3a2c4e5b6d7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_NAME = 'ck_users_balance_no_negativo'


def upgrade() -> None:
    negativos = op.get_bind().execute(
        sa.text("SELECT id, balance FROM users WHERE balance < 0 ORDER BY id")
    ).fetchall()

    if negativos:
        detalle = ", ".join("id=%s saldo=%s" % (fila[0], fila[1]) for fila in negativos)
        raise RuntimeError(
            "Hay usuarios con saldo negativo y no se puede aplicar el CHECK: %s. "
            "Revisá esos saldos a mano (pueden venir del exploit de monto negativo en Crash) "
            "y volvé a correr la migración." % detalle
        )

    op.create_check_constraint(CONSTRAINT_NAME, 'users', 'balance >= 0')


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, 'users', type_='check')
