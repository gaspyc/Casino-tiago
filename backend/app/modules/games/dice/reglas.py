"""Dice: sale un número de 0,00 a 99,99 y vos elegís contra qué apostar.

El jugador pone un objetivo y un lado —menor o mayor— y el multiplicador sale
de la chance que eligió. No hay tabla escrita a mano: el pago es

    multiplicador = RTP / probabilidad de ganar

y con eso el RTP es exactamente el mismo para todas las apuestas posibles,
desde la de 98,99% de chance hasta la de 0,10%. Eso no se estima: las salidas
son 10.000 enteros y se enumeran todas en los tests.

Por qué la ventaja es 1% y no 4%
--------------------------------
El resto del casino corre al 4% (plinko, mines, generala). Acá no, y hay dos
razones concretas, no de gusto:

1. Con 4%, el multiplicador de una apuesta de 96% de chance sería 0,9999x: una
   apuesta que **no puede ganar nunca**. O sea que a 4% habría que prohibir
   todo el tramo de 96% a 99% de chance, que es la mitad de lo que la gente
   viene a jugar al dice. A 1% ese tramo existe y paga 1,0001x a 1,0202x.
2. Limbo —el juego hermano— usa exactamente la distribución del crash, que ya
   corre al 1%. A 4%, limbo sería la misma apuesta que el crash pero pagando
   peor: dominado, nadie lo jugaría entendiendo los dos.

Queda anotado que el casino tiene ahora ventajas de 1% a 4,25% según el juego,
y que eso merece una decisión de conjunto.

Los límites
-----------
El multiplicador se acota **restringiendo la chance que se puede elegir**, no
recortando el pago. Es la diferencia que importa: un tope sobre el pago se
come el RTP sin avisar cuando la jugada lo toca —el bug que tuvo el mines—,
mientras que restringir la entrada deja el RTP exacto para todo lo que sí se
puede apostar.
"""

from fractions import Fraction

__all__ = [
    "CHANCE_MAXIMA",
    "CHANCE_MINIMA",
    "MULTIPLICADOR_MAXIMO",
    "RTP",
    "SALIDAS",
    "chance_de",
    "multiplicador_de",
    "objetivo_valido",
    "paga",
]

# Las salidas son los enteros de 0 a 9999, que se muestran como 0,00 a 99,99.
SALIDAS = 10_000

RTP = Fraction(99, 100)

# Los extremos de chance que se pueden elegir, en cantidad de salidas ganadoras.
# El mínimo fija el multiplicador más alto: 99/0,001 = 990x.
# El máximo existe porque arriba de RTP el multiplicador sería menor a 1x, o
# sea una apuesta que pierde plata siempre gane o pierda.
CHANCE_MINIMA = 10        # 0,10%  -> 990x
CHANCE_MAXIMA = 9_899     # 98,99% -> 1,0001x

MULTIPLICADOR_MAXIMO = RTP * SALIDAS / CHANCE_MINIMA  # 990

MENOR = "menor"
MAYOR = "mayor"
LADOS = (MENOR, MAYOR)


def ganadoras(objetivo: int, lado: str) -> int:
    """Cuántas de las 10.000 salidas ganan con esta apuesta.

    `objetivo` va en centésimas: 4250 es 42,50.
    """
    if lado == MENOR:
        # Gana si la salida es estrictamente menor: 0 .. objetivo-1.
        return objetivo

    if lado == MAYOR:
        # Gana si es estrictamente mayor: objetivo+1 .. 9999.
        return SALIDAS - 1 - objetivo

    raise ValueError("El lado tiene que ser %r o %r" % (MENOR, MAYOR))


def objetivo_valido(objetivo: int, lado: str) -> bool:
    """¿Esta apuesta está dentro de los límites?"""
    if lado not in LADOS:
        return False

    if not 0 <= objetivo < SALIDAS:
        return False

    return CHANCE_MINIMA <= ganadoras(objetivo, lado) <= CHANCE_MAXIMA


def chance_de(objetivo: int, lado: str) -> Fraction:
    """La probabilidad exacta de ganar. Sin flotantes."""
    return Fraction(ganadoras(objetivo, lado), SALIDAS)


def multiplicador_de(objetivo: int, lado: str) -> Fraction:
    """El multiplicador exacto: RTP sobre la chance.

    Es lo que hace que el RTP no dependa de qué apuesta elijas: pagar RTP/p
    cuando ganás con probabilidad p devuelve p * RTP/p = RTP, siempre.
    """
    chance = chance_de(objetivo, lado)
    if chance <= 0:
        raise ValueError("Esa apuesta no puede ganar nunca")

    return RTP / chance


def paga(salida: int, objetivo: int, lado: str) -> bool:
    """¿La salida gana contra esta apuesta?"""
    if lado == MENOR:
        return salida < objetivo

    if lado == MAYOR:
        return salida > objetivo

    raise ValueError("El lado tiene que ser %r o %r" % (MENOR, MAYOR))


def como_texto(valor: int) -> str:
    """4250 -> "42.50". Las salidas y los objetivos van en centésimas."""
    return "%d.%02d" % (valor // 100, valor % 100)
