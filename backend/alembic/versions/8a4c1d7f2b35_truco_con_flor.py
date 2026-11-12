"""Opcion de jugar el truco con flor

Revision ID: 8a4c1d7f2b35
Revises: 7e2a5b94c6f1
Create Date: 2026-11-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8a4c1d7f2b35'
down_revision: Union[str, Sequence[str], None] = '7e2a5b94c6f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'truco_partidas',
        sa.Column('con_flor', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_column('truco_partidas', 'con_flor')
