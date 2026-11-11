"""Movimientos de saldo atómicos.

El saldo se modifica siempre con un UPDATE condicional, nunca leyendo el objeto,
comparando en Python y reescribiéndolo. Ese patrón dejaba una ventana entre la
validación y el commit: dos requests en paralelo leían el mismo saldo, las dos
pasaban el chequeo y las dos cobraban.
"""

from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.infrastructure.models import User


async def debit(db: AsyncSession, user_id: int, amount: Decimal) -> bool:
    """Descuenta `amount` sólo si el saldo alcanza. Devuelve False si no.

    La condición viaja dentro del UPDATE: Postgres bloquea la fila y reevalúa el
    saldo ya commiteado, así que de dos apuestas simultáneas sólo una gana.
    """
    if amount <= 0:
        raise ValueError("El monto a debitar debe ser positivo")

    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.balance >= amount)
        .values(balance=User.balance - amount)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


async def credit(db: AsyncSession, user_id: int, amount: Decimal) -> bool:
    """Acredita `amount` al usuario. Devuelve False si el usuario no existe."""
    if amount <= 0:
        raise ValueError("El monto a acreditar debe ser positivo")

    result = await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(balance=User.balance + amount)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1
