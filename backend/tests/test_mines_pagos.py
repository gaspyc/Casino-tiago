"""Los pagos del mines, medidos por enumeración y no por simulación.

Esto no necesita base: es matemática del módulo de pagos.
"""

from decimal import Decimal
from fractions import Fraction
from itertools import combinations
from math import comb

import pytest

from app.modules.games.mines.paytable import (
    APUESTA_MAXIMA,
    CASILLAS,
    MAXIMO_MULTIPLICADOR,
    MAX_MINAS,
    MIN_MINAS,
    RTP,
    multiplicador,
    premio,
    probabilidad_de_sobrevivir,
    tabla_de_multiplicadores,
)

APUESTA = Decimal("100.00")

TODAS = [
    (minas, k)
    for minas in range(MIN_MINAS, MAX_MINAS + 1)
    for k in range(1, CASILLAS - minas + 1)
]


def test_son_trescientas_combinaciones():
    """Si esto cambia, los tests de abajo dejaron de cubrir todo el juego."""
    assert len(TODAS) == 300


# ------------------------------ las probabilidades ------------------------------

def test_la_probabilidad_sale_de_contar_grillas():
    """Contraste contra el conteo directo, sin usar la fórmula."""
    for minas in (1, 3, 7):
        for k in (1, 2, 3):
            # Grillas posibles: dónde van las minas entre las 25 casillas.
            grillas = list(combinations(range(CASILLAS), minas))
            limpias_las_primeras = sum(
                1 for grilla in grillas if not set(grilla) & set(range(k))
            )

            esperado = Fraction(limpias_las_primeras, len(grillas))
            assert probabilidad_de_sobrevivir(minas, k) == esperado


def test_destapar_de_mas_o_de_menos_no_existe():
    with pytest.raises(ValueError):
        probabilidad_de_sobrevivir(3, 23)  # sólo hay 22 limpias

    with pytest.raises(ValueError):
        probabilidad_de_sobrevivir(0, 1)

    with pytest.raises(ValueError):
        probabilidad_de_sobrevivir(25, 1)


# ------------------------------ el RTP ------------------------------

def test_cada_casillero_paga_exactamente_el_96_por_ciento():
    """La propiedad central: el precio es el justo por 0,96, en todos lados."""
    peor = 0.0

    for minas, k in TODAS:
        probabilidad = float(probabilidad_de_sobrevivir(minas, k))
        devuelto = float(premio(APUESTA, minas, k)) / float(APUESTA)
        peor = max(peor, abs(devuelto * probabilidad - float(RTP)))

    # Lo único que separa del 96% exacto es el redondeo a centavos.
    assert peor < 0.0001, "desvio de %.6f puntos de RTP" % peor


def test_ninguna_forma_de_jugar_cambia_el_rtp():
    """Enumerando todas las estrategias de corte, no simulando.

    Una estrategia acá es "cobro al llegar a k aciertos". Cualquier otra, por
    más vueltas que dé, es una mezcla de éstas, así que si todas dan 96% no hay
    forma de jugar que gane ni que pierda de más.
    """
    for minas in range(MIN_MINAS, MAX_MINAS + 1):
        limpias = CASILLAS - minas

        for corte in range(1, limpias + 1):
            probabilidad = probabilidad_de_sobrevivir(minas, corte)
            esperado = float(probabilidad) * float(premio(APUESTA, minas, corte))

            assert abs(esperado / float(APUESTA) - float(RTP)) < 0.0001, (
                "con %s minas cortando en %s" % (minas, corte)
            )


def test_el_valor_esperado_no_cambia_por_destapar_una_mas():
    """Seguir o cobrar da lo mismo: por eso no hay estrategia.

    Cobrar ahora paga P(k) por premio(k). Seguir una más paga P(k+1) por
    premio(k+1), y los dos tienen que valer lo mismo visto desde el principio.
    """
    for minas, k in TODAS:
        limpias = CASILLAS - minas
        if k == limpias:
            continue

        ahora = float(probabilidad_de_sobrevivir(minas, k)) * float(
            premio(APUESTA, minas, k)
        )
        una_mas = float(probabilidad_de_sobrevivir(minas, k + 1)) * float(
            premio(APUESTA, minas, k + 1)
        )

        assert abs(ahora - una_mas) < 0.02, "con %s minas en el acierto %s" % (minas, k)


# ------------------------------ los números que se muestran ------------------------------

def test_el_multiplicador_mostrado_nunca_promete_mas_de_lo_que_paga():
    for minas, k in TODAS:
        mostrado = multiplicador(minas, k) * APUESTA
        pagado = premio(APUESTA, minas, k)

        assert mostrado <= pagado, "con %s minas en el acierto %s" % (minas, k)
        # Y tampoco se queda corto por más de un centavo por peso apostado.
        assert pagado - mostrado <= APUESTA / 100


def test_los_multiplicadores_suben_con_cada_acierto():
    for minas in range(MIN_MINAS, MAX_MINAS + 1):
        tabla = tabla_de_multiplicadores(minas)
        assert tabla[0] == Decimal("1.00")
        assert all(b > a for a, b in zip(tabla[1:], tabla[2:]))


def test_mas_minas_paga_mas_por_el_mismo_acierto():
    for k in range(1, 10):
        pagos = [
            multiplicador(minas, k)
            for minas in range(MIN_MINAS, MAX_MINAS + 1)
            if CASILLAS - minas >= k
        ]
        assert all(b > a for a, b in zip(pagos, pagos[1:]))


# ------------------------------ los topes ------------------------------

def test_el_tope_de_multiplicador_no_bindea_nunca():
    """Si bindeara, el RTP de esa estrategia caería sin avisar.

    El más grande que la grilla puede dar es 12 minas con las 13 limpias
    destapadas. El tope tiene que estar arriba de eso.
    """
    mayor = max(tabla_de_multiplicadores(minas)[-1] for minas in range(1, 25))

    assert mayor < MAXIMO_MULTIPLICADOR
    assert mayor == multiplicador(12, 13)
    assert mayor == multiplicador(13, 12)


def test_la_exposicion_maxima_de_la_casa_es_la_que_se_cree():
    """Lo peor que puede pasar, con número, no con intuición."""
    peor_multiplicador = multiplicador(12, 13)
    peor_pago = premio(APUESTA_MAXIMA, 12, 13)
    chance = probabilidad_de_sobrevivir(12, 13)

    assert peor_multiplicador > Decimal("4900000")
    assert peor_pago > Decimal("2000000000")
    # Una en 5,2 millones, y sólo si el jugador limpia el tablero entero.
    assert comb(13, 13) / comb(25, 13) == float(chance)
    assert 1 / float(chance) > 5_000_000
