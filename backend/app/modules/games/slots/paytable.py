"""Tabla de pagos de las slots.

Vive separada del servicio para que el RTP se pueda medir sin base de datos.

El espacio de resultados es chico y equiprobable (7 símbolos, 3 rodillos = 343
combinaciones), así que el RTP sale exacto enumerándolo entero, sin simular:

      7 triples, que suman                                       110
    126 líneas con dos símbolos iguales, a 1x                    126
     90 líneas de tres distintos con una cereza, a 1x             90
                                                                 ---
    RTP = 326 / 343 = 95.04%

Paga algo en 223 de cada 343 tiradas (65%), contra 25 de cada 343 (7.3%) de la
tabla vieja, que rendía 77.55%. Casi todo el presupuesto se fue a los premios
frecuentes: con 343 combinaciones no entran un jackpot grande y una frecuencia
alta al mismo tiempo. La alternativa era dejar el jackpot en 100x sin premio por
cereza suelta, con el mismo RTP pero pagando en el 38.8% de las tiradas. Para
tener las dos cosas hay que agrandar el espacio de resultados (más rodillos o
más símbolos), no retocar la tabla.

Los multiplicadores son enteros a propósito: son brutos, incluyen la apuesta, y
con la apuesta mínima de 0.01 un 0.5x daría medio centavo, que no entra en el
NUMERIC(10,2) de la base.

Ojo con la lectura del par a 1x: devuelve la apuesta, no gana nada. Conviene que
la UI lo muestre como "recuperaste" y no como un premio.
"""

from decimal import Decimal

from app.modules.games.shared import rng

CEREZA = "🍒"
SLOT_SYMBOLS = [CEREZA, "🍋", "🍊", "🍇", "🔔", "💎", "7️⃣"]
RODILLOS = 3

MULTIPLICADORES_POR_TRIPLE = {
    "7️⃣": Decimal("40.0"),
    "💎": Decimal("25.0"),
    "🔔": Decimal("15.0"),
    "🍇": Decimal("10.0"),
    "🍊": Decimal("8.0"),
    "🍋": Decimal("7.0"),
    CEREZA: Decimal("5.0"),
}

# Dos símbolos iguales: devuelve la apuesta. Es el premio más frecuente (36.7%).
MULTIPLICADOR_PAR = Decimal("1.0")

# Tres distintos con una cereza: también devuelve la apuesta (26.2%).
MULTIPLICADOR_CEREZA_SUELTA = Decimal("1.0")

SIN_PREMIO = Decimal("0.0")


def girar() -> list:
    """Una tirada: un símbolo por rodillo."""
    return [rng.choice(SLOT_SYMBOLS) for _ in range(RODILLOS)]


def calcular_multiplicador(linea: list) -> Decimal:
    """Cuánto paga una línea, incluida la apuesta (2.0 = devuelve el doble)."""
    if linea[0] == linea[1] == linea[2]:
        return MULTIPLICADORES_POR_TRIPLE.get(linea[0], SIN_PREMIO)

    # Tres símbolos con sólo dos distintos es exactamente un par.
    if len(set(linea)) == 2:
        return MULTIPLICADOR_PAR

    if CEREZA in linea:
        return MULTIPLICADOR_CEREZA_SUELTA

    return SIN_PREMIO
