"""Validación de montos de apuesta compartida entre juegos.

Los juegos por WebSocket reciben el monto directo del cliente, sin pasar por un
schema de Pydantic, así que la validación tiene que hacerse acá antes de tocar
el saldo del usuario.
"""

from decimal import ROUND_DOWN, Decimal, InvalidOperation
from typing import Optional

CENTS = Decimal("0.01")
MIN_BET = Decimal("0.01")
MAX_BET = Decimal("10000.00")


def parse_bet_amount(
    raw_amount,
    min_bet: Decimal = MIN_BET,
    max_bet: Decimal = MAX_BET,
) -> Optional[Decimal]:
    """Convierte un monto recibido del cliente en un Decimal válido.

    Devuelve None si el valor no es un número finito o si queda fuera de los
    límites permitidos. Eso incluye negativos, cero, NaN, infinito y cualquier
    cosa que no sea numérica.
    """
    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError, TypeError):
        return None

    if not amount.is_finite():
        return None

    # El rango se valida antes de redondear para que un exponente gigante no
    # llegue nunca al quantize.
    if amount < min_bet or amount > max_bet:
        return None

    return amount.quantize(CENTS, rounding=ROUND_DOWN)
