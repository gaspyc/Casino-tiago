"""Las reglas del limbo, que es el crash de un jugador.

Lo que hay que demostrar acá es que P(sorteado >= x) * x da 0,99 para TODOS
los objetivos, y que eso no se cumple sólo aproximadamente: el crash point se
trunca a dos decimales y el uniforme es discreto, así que la igualdad podría
romperse en algún objetivo suelto. Se verifican los 99.900.
"""

from decimal import Decimal
from fractions import Fraction

import pytest

try:
    from app.modules.games.crash.fairness import (
        MAX_CRASH_POINT,
        PROBABILIDAD_DE_PAGO,
        calcular_crash_point,
    )
    from app.modules.games.limbo import reglas
    from app.modules.games.shared import pagos
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip("No se pudo importar (%s)" % exc, allow_module_level=True)


TODOS = range(reglas.OBJETIVO_MINIMO, reglas.OBJETIVO_MAXIMO + 1)


# ------------------------------ el RTP ------------------------------

def test_el_rtp_es_al_menos_el_declarado_en_todos_los_objetivos():
    """Los 99.900 objetivos, uno por uno. Y nunca por debajo del 99%.

    Que el desvío caiga siempre del lado del jugador no es casualidad: viene
    de que la cuenta de salidas ganadoras usa un floor y después suma uno, o
    sea que redondea la chance para arriba. Del otro lado la casa estaría
    cobrando una ventaja que no declara.
    """
    peor = None

    for objetivo in TODOS:
        rtp = reglas.chance_de(objetivo) * reglas.multiplicador_de(objetivo)
        assert rtp >= reglas.RTP, (objetivo, float(rtp))

        if peor is None or rtp > peor:
            peor = rtp

    # Y el desvío es despreciable: una parte en diez billones.
    assert peor - reglas.RTP < Fraction(1, 10 ** 12), float(peor - reglas.RTP)


def test_la_ventaja_sale_del_crash_y_no_de_una_constante_propia():
    """Son el mismo juego: si se separaran, un cambio en uno dejaría al otro
    pagando distinto por la misma apuesta."""
    assert reglas.RTP == Fraction(str(PROBABILIDAD_DE_PAGO))
    assert reglas.calcular_crash_point is calcular_crash_point


def test_la_chance_se_parece_a_la_formula_de_manual():
    """P(crash >= x) = 0.99 / x. La cuenta exacta tiene que rondar eso."""
    for objetivo in (101, 150, 200, 1000, 10_000, 100_000):
        exacta = reglas.chance_de(objetivo)
        manual = reglas.RTP / Fraction(objetivo, 100)
        assert abs(exacta - manual) < Fraction(1, 10 ** 12), objetivo


# ------------------------------ los límites ------------------------------

def test_los_objetivos_fuera_de_rango_se_rechazan():
    assert not reglas.objetivo_valido(100)      # 1,00x no paga nada
    assert not reglas.objetivo_valido(reglas.OBJETIVO_MAXIMO + 1)
    assert reglas.objetivo_valido(reglas.OBJETIVO_MINIMO)
    assert reglas.objetivo_valido(reglas.OBJETIVO_MAXIMO)


def test_el_objetivo_maximo_es_el_techo_del_crash():
    """Pedir más que el techo sería una apuesta que no puede ganar nunca."""
    assert reglas.OBJETIVO_MAXIMO == int(MAX_CRASH_POINT * 100)


def test_la_chance_fuera_de_rango_explota():
    with pytest.raises(ValueError):
        reglas.chance_de(100)


def test_mas_objetivo_es_menos_chance():
    anterior = None
    for objetivo in (101, 200, 500, 1000, 5000, 100_000):
        chance = reglas.chance_de(objetivo)
        if anterior is not None:
            assert chance < anterior
        anterior = chance


# ------------------------------ el sorteo ------------------------------

def test_el_sorteo_respeta_el_techo_y_el_piso():
    for nonce in range(500):
        sorteado = calcular_crash_point("server-limbo", "cliente", nonce)
        assert 1.00 <= sorteado <= MAX_CRASH_POINT


def test_paga_compara_contra_el_objetivo():
    assert reglas.paga(2.50, 250)
    assert reglas.paga(2.51, 250)
    assert not reglas.paga(2.49, 250)


def test_la_frecuencia_medida_se_parece_a_la_chance_calculada():
    """Cruce entre la cuenta exacta y el sorteo de verdad.

    Si la fórmula de `chance_de` no describiera lo que hace
    `calcular_crash_point`, acá se vería.
    """
    vueltas = 20_000

    for objetivo in (150, 200, 500):
        ganadas = sum(
            1
            for nonce in range(vueltas)
            if reglas.paga(calcular_crash_point("server-freq", "cli", nonce), objetivo)
        )
        esperadas = float(reglas.chance_de(objetivo)) * vueltas
        desvio = (esperadas * (1 - esperadas / vueltas)) ** 0.5

        assert abs(ganadas - esperadas) < 5 * desvio, (objetivo, ganadas, esperadas)


# ------------------------------ la plata ------------------------------

def test_el_multiplicador_es_el_objetivo():
    assert reglas.multiplicador_de(250) == Fraction(250, 100)
    assert pagos.premio(Decimal("100.00"), reglas.multiplicador_de(250)) == Decimal("250.00")


def test_el_premio_nunca_redondea_para_arriba():
    for objetivo in (101, 133, 250, 999, 100_000):
        multiplicador = reglas.multiplicador_de(objetivo)
        for apuesta in (Decimal("0.07"), Decimal("3.33"), Decimal("97.77")):
            exacto = (
                Decimal(multiplicador.numerator)
                * apuesta
                / Decimal(multiplicador.denominator)
            )
            assert pagos.premio(apuesta, multiplicador) <= exacto


def test_como_texto_muestra_dos_decimales():
    assert reglas.como_texto(101) == "1.01"
    assert reglas.como_texto(250) == "2.50"
    assert reglas.como_texto(100_000) == "1000.00"
