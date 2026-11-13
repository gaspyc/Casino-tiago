"""La tabla de pagos de la generala contra la casa: se cobra por puntaje.

Por qué no se paga por ganar
----------------------------
Antes esto pagaba 1,95x por ganarle a la casa y nada por perder. Con pago
binario la diferencia de retorno entre un casual y un experto es exactamente
la diferencia de habilidad **amplificada**, porque ganar o perder es un umbral
y cerca del umbral unos pocos puntos deciden toda la apuesta. Medido: al que
jugaba al máximo le volvía el 93,9% y al que jugaba como en una mesa de casa
el 68,6%. Una brecha de 1,37x sobre una diferencia de puntaje de apenas 1,20x.

Pagando por puntaje la brecha baja a la diferencia de puntaje y nada más. El
casual pasa de dejar el 31% a dejar el 20%.

La forma del pago
-----------------
    multiplicador = puntaje / PUNTAJE_DE_EQUILIBRIO   (+ PREMIO_SERVIDA)

Es una recta por el origen, sin umbral, y eso no es estética: es lo que hace
que el techo de la casa se pueda calcular exacto.

El umbral es lo primero que uno quiere poner —"abajo de 100 no paga nada"— y
es justo lo que no hay que hacer. Medido, con umbral 80 la brecha sube a
1,51x y con umbral 100 a 1,70x: **peor que el pago binario que se quería
arreglar**. Un umbral es otra vez un acantilado, y el casual se cae más
seguido. La varianza que da sale carísima.

El techo
--------
Con pago afín, maximizar el pago esperado es maximizar el puntaje esperado, y
el puntaje esperado del juego perfecto se resuelve exacto en `optimo.py`:
149,17 puntos sin premio, 167,23 cuidando la generala para cazar el premio.
Ese número es el que fija `PUNTAJE_DE_EQUILIBRIO`.

Importa que sea exacto. La mejor política que yo había programado a mano saca
139,4 puntos, un 6,5% por debajo del óptimo: calibrar con ella habría puesto
al jugador perfecto en 102,7% y la casa pierde plata con cada partida. Es la
misma clase de error que el tope del mines, y acá se evita resolviendo el
juego en vez de estimarlo.

El premio por servida
---------------------
Sin premio el juego no tiene varianza: todas las partidas pagan entre 0,3x y
1,6x, que es una máquina de devolver la apuesta. El premio por anotar la
generala servida es lo que le da un golpe grande, y cuesta poca brecha porque
en términos absolutos es chico para los dos lados.

No es gratis en exactitud: con premio, el juego perfecto cambia y cuida la
fila de la generala para conservar la chance. Por eso el techo se calcula con
`optimo.techo_del_pago`, que incluye ese cambio de política. Calcularlo sin
eso daba un techo corto.

Lo que da
---------
Medido sobre 400.000 planillas por política, con el techo resuelto exacto:

    politica                 puntos    RTP     del puntaje   del premio
    --------------------------------------------------------------------
    juego perfecto (exacto)   149,1   95,56%
    calculadora (1 tirada)    140,0   91,2%       80,0%         11,2%
    bot de la casa            141,4   89,5%       80,8%          8,7%
    heuristica (casual)       124,3   82,1%       71,0%         11,1%
    azarosa (piso)             51,9   31,8%       29,7%          2,1%

    brecha perfecto/casual             1,164x   antes era 1,37x
    desvio estandar del pago            1,40

El casual pasa de dejar el 31,4% a dejar el 17,9%, y la ventaja de la casa
contra el mejor jugador posible queda fijada y conocida —4,44%— en vez de
estimada con el mejor bot que uno pudo escribir.

El premio aporta el 13% del RTP: alcanza para que el juego tenga un golpe
grande sin que el puntaje deje de ser lo que manda.

Lo que se resignó: casi ninguna partida paga más de 1x por puntaje solo —un
casual pasa de 175 puntos una de cada nueve— y el resto cobra entre 0,4x y
0,95x. Es el precio de no poner umbral, y es a propósito: con umbral habría
más partidas ganadoras y una brecha peor que la que se vino a arreglar.

Los números de arriba se reproducen con:

    python -m app.modules.games.generala.simular pagos
"""

from decimal import ROUND_DOWN, Decimal
from fractions import Fraction

__all__ = [
    "APUESTA_MAXIMA",
    "PREMIO_SERVIDA",
    "PUNTAJE_DE_EQUILIBRIO",
    "RTP_OBJETIVO",
    "multiplicador",
    "premio",
]

# El puntaje que devuelve exactamente la apuesta. Es la forma legible de
# escribir la pendiente: un punto vale 1/PUNTAJE_DE_EQUILIBRIO de la apuesta.
PUNTAJE_DE_EQUILIBRIO = 175

# Lo que paga aparte anotar la generala servida, sumado al pago por puntaje.
PREMIO_SERVIDA = Decimal("17")

# Lo que le vuelve al que juega perfecto. La ventaja de la casa es el resto.
RTP_OBJETIVO = Decimal("0.96")

APUESTA_MAXIMA = Decimal("500.00")

CENTAVOS = Decimal("0.01")


def _factor(puntaje: int, servida: bool) -> Fraction:
    """El multiplicador exacto, sin redondear. Es lo que se usa para pagar."""
    if puntaje < 0:
        raise ValueError("El puntaje no puede ser negativo")

    factor = Fraction(puntaje, PUNTAJE_DE_EQUILIBRIO)
    if servida:
        factor += Fraction(PREMIO_SERVIDA)

    return factor


def premio(apuesta: Decimal, puntaje: int, servida: bool = False) -> Decimal:
    """Lo que se paga, en pesos. Redondeado una sola vez y al final.

    El premio sale de la fracción exacta, no del multiplicador mostrado.
    Truncar el multiplicador y recién después multiplicar se come RTP en los
    pagos chicos: en el mines esa diferencia eran 0,7 puntos.
    """
    factor = _factor(puntaje, servida)
    exacto = Decimal(factor.numerator) * Decimal(apuesta) / Decimal(factor.denominator)
    return exacto.quantize(CENTAVOS, rounding=ROUND_DOWN)


def multiplicador(puntaje: int, servida: bool = False) -> Decimal:
    """El multiplicador para mostrar. No es con lo que se paga."""
    factor = _factor(puntaje, servida)
    return (
        Decimal(factor.numerator) / Decimal(factor.denominator)
    ).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)


def tabla_de_referencia() -> list:
    """Unos puntajes de muestra, para la pantalla y para la API."""
    return [
        {"puntaje": puntaje, "multiplicador": str(multiplicador(puntaje))}
        for puntaje in (60, 100, PUNTAJE_DE_EQUILIBRIO, 200, 250)
    ]
