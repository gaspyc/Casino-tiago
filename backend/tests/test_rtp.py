"""RTP de ruleta y slots.

El RTP no se estima acá: los dos juegos tienen un espacio de resultados chico y
equiprobable (37 números, 343 combinaciones de rodillos), así que se calcula
exacto enumerándolo entero con fracciones. Un Monte Carlo daría un número peor
y encima flaky.

La simulación queda para lo único que la enumeración no cubre: que el RNG
realmente produzca la distribución uniforme que la enumeración da por supuesta.
"""

from collections import Counter
from decimal import Decimal
from fractions import Fraction
from itertools import product

import pytest

from app.modules.games.roulette import paytable as ruleta
from app.modules.games.slots import paytable as slots
from app.modules.games.shared import rng

# Ruleta europea de un solo cero: la casa se queda con 1 de 37.
RTP_RULETA_EUROPEA = Fraction(36, 37)

# Tabla de pagos de las slots. Ver el docstring de slots/paytable.py.
RTP_SLOTS = Fraction(326, 343)

# Cuántas de las 343 combinaciones pagan algo.
COMBINACIONES_PREMIADAS = 223

APUESTAS_DE_RULETA = [
    ("number", "0"),
    ("number", "17"),
    ("number", "36"),
    ("color", "red"),
    ("color", "black"),
    ("parity", "even"),
    ("parity", "odd"),
    ("split", "1,2"),
    ("split", "0,3"),
    ("split", "33,36"),
    ("corner", "1,2,4,5"),
    ("corner", "0,1,2,3"),
    ("corner", "32,33,35,36"),
    ("dozen", "1"),
    ("dozen", "2"),
    ("dozen", "3"),
    ("column", "1"),
    ("column", "2"),
    ("column", "3"),
    ("half", "low"),
    ("half", "high"),
]


def _rtp_de_la_apuesta(bet_type: str, bet_value: str) -> Fraction:
    """Devuelto esperado por unidad apostada, sobre la rueda entera."""
    devuelto = sum(
        Fraction(ruleta.calcular_multiplicador(bet_type, bet_value, numero))
        for numero in ruleta.ROULETTE_NUMBERS
    )
    return Fraction(devuelto, len(ruleta.ROULETTE_NUMBERS))


def _todas_las_lineas():
    return [list(combo) for combo in product(slots.SLOT_SYMBOLS, repeat=slots.RODILLOS)]


def _rtp_de_las_slots() -> Fraction:
    lineas = _todas_las_lineas()
    devuelto = sum(Fraction(slots.calcular_multiplicador(linea)) for linea in lineas)
    return Fraction(devuelto, len(lineas))


# ------------------------------- ruleta -------------------------------

@pytest.mark.parametrize("bet_type, bet_value", APUESTAS_DE_RULETA)
def test_rtp_exacto_de_la_ruleta(bet_type, bet_value):
    """97.30% para cada tipo de apuesta, que es lo correcto para un solo cero."""
    assert _rtp_de_la_apuesta(bet_type, bet_value) == RTP_RULETA_EUROPEA


def test_ninguna_apuesta_de_la_ruleta_paga_mejor_que_otra():
    """Si una pagara distinto, sería la apuesta óptima y rompería la mesa."""
    rtps = {_rtp_de_la_apuesta(tipo, valor) for tipo, valor in APUESTAS_DE_RULETA}

    assert rtps == {RTP_RULETA_EUROPEA}


def test_la_ventaja_de_la_casa_sale_del_cero():
    for tipo, valor in APUESTAS_DE_RULETA:
        if tipo in ("number", "split", "corner"):
            continue  # estas sí pueden cubrir el cero
        assert ruleta.calcular_multiplicador(tipo, valor, 0) == Decimal("0.0")


def test_cada_numero_paga_una_sola_docena_y_una_sola_columna():
    for numero in range(1, 37):
        docenas = [d for d in "123" if ruleta.calcular_multiplicador("dozen", d, numero) > 0]
        columnas = [c for c in "123" if ruleta.calcular_multiplicador("column", c, numero) > 0]

        assert len(docenas) == 1
        assert len(columnas) == 1


# ------------------------------- slots -------------------------------

def test_rtp_exacto_de_las_slots():
    """95.04%, dentro del 92-97% que paga la industria.

    El número está acá para que retocar la tabla sea una decisión explícita y
    no un accidente: si se toca un multiplicador, este test falla.
    """
    assert len(_todas_las_lineas()) == 343
    assert _rtp_de_las_slots() == RTP_SLOTS
    assert float(RTP_SLOTS) == pytest.approx(0.9504, abs=0.0001)


def test_las_slots_pagan_algo_en_dos_de_cada_tres_tiradas():
    """El objetivo del rediseño: premios chicos y frecuentes.

    La tabla anterior pagaba en 25 de 343 tiradas (7.3%).
    """
    premiadas = [
        linea for linea in _todas_las_lineas()
        if slots.calcular_multiplicador(linea) > 0
    ]

    assert len(premiadas) == COMBINACIONES_PREMIADAS
    assert Fraction(len(premiadas), 343) > Fraction(6, 10)


def test_los_multiplicadores_son_enteros():
    """Con la apuesta mínima de 0.01, medio multiplicador daría medio centavo."""
    for linea in _todas_las_lineas():
        multiplicador = slots.calcular_multiplicador(linea)
        assert multiplicador == multiplicador.to_integral_value()


def test_de_donde_sale_el_rtp_de_las_slots():
    """Desglose por premio, para saber qué mover si se retoca la tabla."""
    lineas = _todas_las_lineas()

    def _aporte(condicion):
        return sum(
            Fraction(slots.calcular_multiplicador(linea))
            for linea in lineas
            if condicion(linea)
        )

    es_triple = lambda l: l[0] == l[1] == l[2]
    es_par = lambda l: not es_triple(l) and len(set(l)) == 2
    es_cereza_suelta = lambda l: len(set(l)) == 3 and slots.CEREZA in l

    triples = _aporte(es_triple)
    pares = _aporte(es_par)
    cerezas_sueltas = _aporte(es_cereza_suelta)

    assert triples == 110  # 7 triples, uno por símbolo
    assert pares == 126  # 126 combinaciones a 1x
    assert cerezas_sueltas == 90  # 90 combinaciones a 1x
    assert Fraction(triples + pares + cerezas_sueltas, len(lineas)) == RTP_SLOTS


def test_el_par_paga_en_cualquier_posicion():
    for linea in ([slots.CEREZA, slots.CEREZA, "🍋"],
                  [slots.CEREZA, "🍋", slots.CEREZA],
                  ["🍋", slots.CEREZA, slots.CEREZA]):
        assert slots.calcular_multiplicador(linea) == slots.MULTIPLICADOR_PAR


def test_una_cereza_suelta_devuelve_la_apuesta():
    assert slots.calcular_multiplicador([slots.CEREZA, "🍋", "🍊"]) == Decimal("1.0")
    assert slots.calcular_multiplicador(["🍋", slots.CEREZA, "🍊"]) == Decimal("1.0")


def test_tres_distintos_sin_cereza_no_pagan():
    assert slots.calcular_multiplicador(["🍋", "🍊", "🍇"]) == Decimal("0.0")


# ------------------------- uniformidad del RNG -------------------------

def test_la_ruleta_saca_los_37_numeros_con_la_misma_frecuencia():
    tiradas = 74_000
    conteo = Counter(rng.choice(ruleta.ROULETTE_NUMBERS) for _ in range(tiradas))
    esperado = tiradas / 37

    assert len(conteo) == 37
    for numero in ruleta.ROULETTE_NUMBERS:
        assert abs(conteo[numero] - esperado) < esperado * 0.15


def test_los_rodillos_sacan_los_7_simbolos_con_la_misma_frecuencia():
    tiradas = 70_000
    conteo = Counter()
    for _ in range(tiradas):
        linea = slots.girar()
        assert len(linea) == slots.RODILLOS
        conteo.update(linea)

    esperado = tiradas * slots.RODILLOS / len(slots.SLOT_SYMBOLS)
    for simbolo in slots.SLOT_SYMBOLS:
        assert abs(conteo[simbolo] - esperado) < esperado * 0.05


def test_la_ruleta_simulada_converge_al_rtp_exacto():
    """Cierra el círculo: la rueda real, no la enumeración, paga 97.3%."""
    tiradas = 200_000
    devuelto = sum(
        ruleta.calcular_multiplicador("color", "red", rng.choice(ruleta.ROULETTE_NUMBERS))
        for _ in range(tiradas)
    )

    rtp = float(devuelto) / tiradas

    assert abs(rtp - float(RTP_RULETA_EUROPEA)) < 0.01


def test_las_slots_simuladas_convergen_al_rtp_exacto():
    """Cierra el círculo: los rodillos reales, no la enumeración, pagan 95%."""
    tiradas = 200_000
    devuelto = sum(slots.calcular_multiplicador(slots.girar()) for _ in range(tiradas))

    rtp = float(devuelto) / tiradas

    assert abs(rtp - float(RTP_SLOTS)) < 0.03
