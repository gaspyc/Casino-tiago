"""Los pagos del mines, exactos.

La grilla tiene 25 casillas y el jugador elige cuántas minas esconde. Destapa
de a una y puede cobrar cuando quiera; si toca una mina pierde la apuesta.

Sobrevivir a k destapes es sacar k casillas limpias seguidas de una grilla con
`minas` minas. La probabilidad es hipergeométrica y sale de contar, no de
simular:

    P(k) = C(25 - minas, k) / C(25, k)

El pago justo sería 1/P(k). El de la casa es ese número por (1 - ventaja), que
es de dónde salen exactamente los 4 puntos de RTP. No hay tabla escrita a mano
ni multiplicadores inventados: se calculan, así que no se pueden desalinear de
las probabilidades como pasó con el plinko.

Lo que hace bueno a este juego: el RTP es 96% para **cualquier** forma de
jugar. Cobrar al primer acierto, ir hasta el final o cortar donde sea, todas
pagan lo mismo a la larga, porque cada multiplicador es el justo por 0,96. No
hay estrategia que mejore ni que empeore las chances, y eso se puede probar
enumerando, no simulando.

Dos números y no uno
--------------------
`premio()` es lo que se paga y sale de la fracción exacta. `multiplicador()` es
el número que se muestra, redondeado a centavos hacia abajo. Se separan porque
redondear el multiplicador y después multiplicar perdía hasta 0,7 puntos de RTP
en los pagos chicos: truncar 1,0956 a 1,09 es medio punto que se come la casa
sin que figure en ningún lado. Así, el premio es exacto y el número de la
pantalla nunca promete de más.
"""

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from fractions import Fraction
from math import comb

__all__ = [
    "APUESTA_MAXIMA",
    "APUESTA_MINIMA",
    "CASILLAS",
    "MAXIMO_MULTIPLICADOR",
    "MAX_MINAS",
    "MIN_MINAS",
    "RTP",
    "VENTAJA_DE_LA_CASA",
    "multiplicador",
    "premio",
    "probabilidad_de_sobrevivir",
    "tabla_de_multiplicadores",
]

CASILLAS = 25
MIN_MINAS = 1
MAX_MINAS = 24

VENTAJA_DE_LA_CASA = Fraction(4, 100)
RTP = 1 - VENTAJA_DE_LA_CASA

# Red de seguridad, no un tope de negocio: está puesto arriba del multiplicador
# más grande que la grilla puede dar (12 minas y las 13 limpias destapadas,
# 4.992.288x, una en 5,2 millones), así que nunca bindea. Existe para que un
# bug no pueda pagar infinito, no para recortar premios.
#
# Un tope que bindeara rompería la propiedad de arriba. Con el tope en 10.000,
# por ejemplo, el que limpia un tablero de 4 minas cobraría 10.000 en vez de
# 12.144 y su RTP real caería a 79%, sin que nada en la pantalla se lo avisara.
# La exposición de la casa se acota con el límite de apuesta, que es visible.
MAXIMO_MULTIPLICADOR = Decimal("5000000")

# Lo que se puede poner en una grilla. Acá sí se acota el riesgo.
APUESTA_MINIMA = Decimal("0.01")
APUESTA_MAXIMA = Decimal("500")

CENTAVO = Decimal("0.01")


def probabilidad_de_sobrevivir(minas: int, destapadas: int) -> Fraction:
    """P(las primeras `destapadas` casillas sean todas limpias). Exacta."""
    _validar(minas, destapadas)

    limpias = CASILLAS - minas
    return Fraction(comb(limpias, destapadas), comb(CASILLAS, destapadas))


def _factor(minas: int, destapadas: int) -> Fraction:
    """El multiplicador como fracción, sin redondear."""
    if destapadas == 0:
        return Fraction(1)

    return RTP / probabilidad_de_sobrevivir(minas, destapadas)


def premio(apuesta: Decimal, minas: int, destapadas: int) -> Decimal:
    """Lo que se paga por cobrar con `destapadas` casillas limpias.

    Sale de la fracción exacta y recién al final se redondea a centavos, así
    el RTP queda en 96% clavado y no en 95,3% por el truncado.
    """
    factor = _factor(minas, destapadas)
    if factor > Fraction(MAXIMO_MULTIPLICADOR):
        factor = Fraction(MAXIMO_MULTIPLICADOR)

    bruto = apuesta * Decimal(factor.numerator) / Decimal(factor.denominator)
    return bruto.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def multiplicador(minas: int, destapadas: int) -> Decimal:
    """El número que se muestra. Hacia abajo: nunca promete más de lo que paga."""
    factor = _factor(minas, destapadas)
    valor = Decimal(factor.numerator) / Decimal(factor.denominator)

    return min(
        valor.quantize(CENTAVO, rounding=ROUND_DOWN),
        MAXIMO_MULTIPLICADOR,
    )


def tabla_de_multiplicadores(minas: int) -> list:
    """Todos los pagos posibles de una grilla, del primer destape al último."""
    _validar(minas, 0)

    limpias = CASILLAS - minas
    return [multiplicador(minas, k) for k in range(limpias + 1)]


def _validar(minas: int, destapadas: int) -> None:
    if not MIN_MINAS <= minas <= MAX_MINAS:
        raise ValueError("Las minas van de %s a %s" % (MIN_MINAS, MAX_MINAS))

    if not 0 <= destapadas <= CASILLAS - minas:
        raise ValueError("No se pueden destapar %s casillas limpias" % destapadas)
