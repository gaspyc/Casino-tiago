"""Limbo: elegís un multiplicador y el juego sortea otro. Si el sorteado
llega, cobrás el tuyo.

Es el crash de un jugador y sin espera: la misma distribución, resuelta en el
acto y sin tener que acertar el momento de cobrar.

Eso no es una casualidad de diseño, es a propósito. `calcular_crash_point` del
crash es la misma función, importada, no copiada. Un jugador que ya aprendió a
verificar una ronda de crash verifica una jugada de limbo con la cuenta que ya
sabe, y la ventaja de la casa no puede quedar distinta entre los dos juegos
por un descuido al tocar una constante.

De la distribución del crash sale P(sorteado >= x) = 0.99 / x, así que apostar
a cualquier objetivo x devuelve x * 0.99 / x = 0.99. El RTP es el mismo para
todos los objetivos, del 1,01x al 1000x.

La parte fina es que esa igualdad es aproximada y no exacta, porque el crash
point se trunca a dos decimales y el uniforme es discreto. El error es de una
parte en 10^13 y siempre del mismo orden, pero el test lo verifica objetivo
por objetivo —los 99.900 que se pueden elegir— en vez de confiar en la
fórmula.
"""

from fractions import Fraction

from app.modules.games.crash.fairness import (
    MAX_CRASH_POINT,
    PROBABILIDAD_DE_PAGO,
    calcular_crash_point,
)

__all__ = [
    "BITS",
    "OBJETIVO_MAXIMO",
    "OBJETIVO_MINIMO",
    "RTP",
    "calcular_crash_point",
    "chance_de",
    "paga",
]

# El RTP sale del crash, no de una constante propia: son el mismo juego y
# tienen que moverse juntos.
RTP = Fraction(str(PROBABILIDAD_DE_PAGO))

# Los objetivos van en centésimas, igual que el crash point: 250 es 2,50x.
OBJETIVO_MINIMO = 101                       # 1,01x
OBJETIVO_MAXIMO = int(MAX_CRASH_POINT * 100)  # 1000,00x

# Los bits del uniforme del crash. Acá hace falta para contar las salidas
# ganadoras exactas en vez de usar la aproximación 0.99/x.
BITS = 52
_ESPACIO = 2 ** BITS


def objetivo_valido(objetivo: int) -> bool:
    return OBJETIVO_MINIMO <= objetivo <= OBJETIVO_MAXIMO


def chance_de(objetivo: int) -> Fraction:
    """La probabilidad exacta de que el crash point llegue al objetivo.

    No es 0.99/x: es la cuenta de los valores del uniforme que ganan. El
    crash point es floor(99 / u) / 100 con u = k / 2^52, así que llega al
    objetivo cuando 99 / u >= objetivo, o sea k <= floor(99 * 2^52 / objetivo).
    Se suma uno porque k = 0 también gana.
    """
    if not objetivo_valido(objetivo):
        raise ValueError("Objetivo fuera de los límites")

    numerador = RTP.numerator * 100 * _ESPACIO  # 99 * 2^52, si RTP = 99/100
    ganadoras = numerador // (RTP.denominator * objetivo) + 1

    return Fraction(min(ganadoras, _ESPACIO), _ESPACIO)


def paga(crash_point: float, objetivo: int) -> bool:
    """¿El multiplicador sorteado llega al objetivo?"""
    return round(crash_point * 100) >= objetivo


def multiplicador_de(objetivo: int) -> Fraction:
    """Lo que paga el objetivo: el objetivo mismo."""
    return Fraction(objetivo, 100)


def como_texto(objetivo: int) -> str:
    """250 -> "2.50"."""
    return "%d.%02d" % (objetivo // 100, objetivo % 100)
