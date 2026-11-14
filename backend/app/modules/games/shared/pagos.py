"""Cómo se convierte un multiplicador en plata, sin perder RTP en el redondeo.

Está compartido porque es el error que se repite en todos los juegos: truncar
el multiplicador para mostrarlo y después multiplicar la apuesta por el número
truncado. Cada juego se come unos centavos por jugada y el RTP real termina
abajo del que dice la tabla. En el mines esa diferencia eran 0,7 puntos.

La regla es una sola: **el premio sale de la fracción exacta y se redondea una
sola vez, al final**. El multiplicador que se muestra es otro número, para la
pantalla, y nunca se usa para pagar.

Y se trunca para abajo, nunca al más cercano: redondear para arriba le estaría
regalando medio centavo por jugada a cada apuesta, que sobre volumen es plata
de verdad y además hace que el RTP medido no cierre con el calculado.
"""

from decimal import ROUND_DOWN, Decimal
from fractions import Fraction

__all__ = ["CENTAVOS", "mostrar", "premio"]

CENTAVOS = Decimal("0.01")


def premio(apuesta: Decimal, factor: Fraction) -> Decimal:
    """Lo que se paga, en pesos. El factor es exacto, no el que se muestra."""
    if factor < 0:
        raise ValueError("El multiplicador no puede ser negativo")

    exacto = Decimal(factor.numerator) * Decimal(apuesta) / Decimal(factor.denominator)
    return exacto.quantize(CENTAVOS, rounding=ROUND_DOWN)


def mostrar(factor: Fraction, decimales: int = 2) -> Decimal:
    """El multiplicador para la pantalla. No es con lo que se paga.

    Se trunca por el mismo motivo: mostrar 2,00x y pagar 1,9999x sería mentir,
    mostrar 2,00x cuando el factor es 2,004x es sólo redondear.
    """
    paso = Decimal(1).scaleb(-decimales)
    return (
        Decimal(factor.numerator) / Decimal(factor.denominator)
    ).quantize(paso, rounding=ROUND_DOWN)
