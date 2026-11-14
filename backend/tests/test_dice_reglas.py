"""Las reglas del dice: el RTP tiene que ser el mismo para toda apuesta.

Acá no se simula nada. Las salidas son 10.000 enteros, así que el RTP de cada
apuesta posible se enumera entero y sale exacto. Si algún día alguien toca la
fórmula del multiplicador, estos tests lo paran antes de que salga.
"""

from decimal import Decimal
from fractions import Fraction

import pytest

try:
    from app.modules.games.dice import reglas
    from app.modules.games.dice.fairness import derivar_salida
    from app.modules.games.shared import pagos
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip("No se pudo importar (%s)" % exc, allow_module_level=True)


def _apuestas_validas():
    for lado in reglas.LADOS:
        for objetivo in range(reglas.SALIDAS):
            if reglas.objetivo_valido(objetivo, lado):
                yield objetivo, lado


# ------------------------------ el RTP ------------------------------

def test_el_rtp_es_exacto_en_todas_las_apuestas_posibles():
    """El corazón del juego: pagar RTP/p devuelve RTP sea cual sea p.

    Se enumeran las 19.780 apuestas que se pueden hacer, no una muestra.
    """
    cuantas = 0

    for objetivo, lado in _apuestas_validas():
        chance = reglas.chance_de(objetivo, lado)
        multiplicador = reglas.multiplicador_de(objetivo, lado)

        assert chance * multiplicador == reglas.RTP, (objetivo, lado)
        cuantas += 1

    assert cuantas > 19_000, cuantas


def test_el_rtp_cierra_enumerando_las_diez_mil_salidas():
    """La otra forma de verlo: se recorren las salidas una por una.

    Es la cuenta que haría un auditor —cuánto paga cada resultado posible—
    en vez de confiar en la fórmula de la probabilidad.
    """
    for objetivo, lado in ((2500, "menor"), (5000, "menor"), (9000, "mayor"), (20, "menor")):
        multiplicador = reglas.multiplicador_de(objetivo, lado)
        devuelto = sum(
            multiplicador
            for salida in range(reglas.SALIDAS)
            if reglas.paga(salida, objetivo, lado)
        )

        assert devuelto / reglas.SALIDAS == reglas.RTP, (objetivo, lado)


def test_la_ventaja_de_la_casa_es_uno_por_ciento():
    assert reglas.RTP == Fraction(99, 100)
    assert 1 - reglas.RTP == Fraction(1, 100)


# ------------------------------ los límites ------------------------------

def test_ninguna_apuesta_permitida_paga_menos_de_uno():
    """Una apuesta con multiplicador < 1x no puede ganar nunca, gane o pierda.

    Es la razón concreta por la que este juego va al 1% y no al 4%: con 4% el
    tramo de 96% a 99% de chance quedaría prohibido, que es la mitad de lo que
    la gente viene a jugar.
    """
    for objetivo, lado in _apuestas_validas():
        assert reglas.multiplicador_de(objetivo, lado) > 1, (objetivo, lado)


def test_ninguna_apuesta_permitida_pasa_el_multiplicador_maximo():
    for objetivo, lado in _apuestas_validas():
        assert reglas.multiplicador_de(objetivo, lado) <= reglas.MULTIPLICADOR_MAXIMO


def test_el_tope_se_pone_en_la_entrada_y_no_en_el_pago():
    """El bug del mines fue recortar el pago: el RTP se caía sin avisar.

    Acá el tope se hace rechazando la apuesta, así que lo que sí se puede
    apostar paga el RTP completo.
    """
    # Justo abajo del mínimo de chance: se rechaza, no se recorta.
    assert not reglas.objetivo_valido(reglas.CHANCE_MINIMA - 1, "menor")
    assert reglas.objetivo_valido(reglas.CHANCE_MINIMA, "menor")

    # Y la que entra paga exacto, sin recorte.
    multiplicador = reglas.multiplicador_de(reglas.CHANCE_MINIMA, "menor")
    assert reglas.chance_de(reglas.CHANCE_MINIMA, "menor") * multiplicador == reglas.RTP


def test_el_multiplicador_maximo_es_990():
    assert reglas.MULTIPLICADOR_MAXIMO == 990
    assert reglas.multiplicador_de(reglas.CHANCE_MINIMA, "menor") == 990


def test_los_extremos_invalidos_se_rechazan():
    assert not reglas.objetivo_valido(0, "menor")       # no gana nunca
    assert not reglas.objetivo_valido(9999, "mayor")    # no gana nunca
    assert not reglas.objetivo_valido(9900, "menor")    # pagaria 1x o menos
    assert not reglas.objetivo_valido(5000, "costado")  # lado inexistente


# ------------------------------ ganadoras y pagos ------------------------------

def test_menor_y_mayor_cuentan_bien_las_salidas():
    assert reglas.ganadoras(2500, "menor") == 2500      # 0 .. 2499
    assert reglas.ganadoras(2500, "mayor") == 7499      # 2501 .. 9999
    # El objetivo exacto no gana de ningun lado: por eso suman 9999 y no 10000.
    assert reglas.ganadoras(2500, "menor") + reglas.ganadoras(2500, "mayor") == 9999


def test_el_objetivo_exacto_no_paga():
    assert not reglas.paga(2500, 2500, "menor")
    assert not reglas.paga(2500, 2500, "mayor")


def test_paga_respeta_el_lado():
    assert reglas.paga(2499, 2500, "menor")
    assert not reglas.paga(2501, 2500, "menor")
    assert reglas.paga(2501, 2500, "mayor")
    assert not reglas.paga(2499, 2500, "mayor")


def test_como_texto_muestra_dos_decimales():
    assert reglas.como_texto(0) == "0.00"
    assert reglas.como_texto(4250) == "42.50"
    assert reglas.como_texto(9999) == "99.99"
    assert reglas.como_texto(705) == "7.05"


# ------------------------------ el sorteo ------------------------------

def test_la_salida_esta_en_rango_y_es_determinista():
    for nonce in range(200):
        salida = derivar_salida("server-de-prueba", "cliente", nonce)
        assert 0 <= salida < reglas.SALIDAS
        assert salida == derivar_salida("server-de-prueba", "cliente", nonce)


def test_cambiar_cualquier_parte_cambia_la_salida():
    base = derivar_salida("server-de-prueba", "cliente", 7)
    distintas = {
        base,
        derivar_salida("otro-server", "cliente", 7),
        derivar_salida("server-de-prueba", "otro-cliente", 7),
        derivar_salida("server-de-prueba", "cliente", 8),
    }
    assert len(distintas) > 1


def test_la_salida_se_reparte_parejo():
    """Chi-cuadrado sobre 100 cajones con 50.000 tiradas.

    No prueba uniformidad —eso lo da el muestreo con rechazo, que es exacto—
    pero atrapa un error grueso en la derivación.
    """
    cajones = [0] * 100
    vueltas = 50_000

    for nonce in range(vueltas):
        cajones[derivar_salida("server-chi", "cliente", nonce) // 100] += 1

    esperado = vueltas / 100
    chi = sum((visto - esperado) ** 2 / esperado for visto in cajones)

    # 99 grados de libertad: el valor critico al 0,1% es ~148.
    assert chi < 148, chi


def test_el_muestreo_con_rechazo_saca_el_sesgo_del_modulo():
    """2^52 no es multiplo de 10.000, asi que el modulo a secas sesgaria.

    El sesgo seria de 1 en 10^13 y nadie lo notaria, pero descartarlo cuesta
    tres lineas y deja el juego exactamente uniforme en vez de casi uniforme.
    """
    from app.modules.games.dice.fairness import _ESPACIO, _LIMITE

    assert _ESPACIO % reglas.SALIDAS != 0, "si fuera multiplo no haria falta"
    assert _LIMITE % reglas.SALIDAS == 0
    assert _LIMITE <= _ESPACIO
    # Lo que se descarta es diminuto, pero existe.
    assert 0 < _ESPACIO - _LIMITE < reglas.SALIDAS


# ------------------------------ la plata ------------------------------

def test_el_premio_sale_de_la_fraccion_y_no_del_multiplicador_mostrado():
    apuesta = Decimal("100.00")
    objetivo, lado = 3333, "menor"

    exacto = reglas.multiplicador_de(objetivo, lado)
    mostrado = pagos.mostrar(exacto, 4)

    assert pagos.premio(apuesta, exacto) >= (mostrado * apuesta).quantize(Decimal("0.01"))


def test_el_premio_nunca_redondea_para_arriba():
    for objetivo in (7, 13, 101, 999, 3333):
        for lado in reglas.LADOS:
            if not reglas.objetivo_valido(objetivo, lado):
                continue
            multiplicador = reglas.multiplicador_de(objetivo, lado)
            for apuesta in (Decimal("0.07"), Decimal("3.33"), Decimal("97.77")):
                exacto = (
                    Decimal(multiplicador.numerator)
                    * apuesta
                    / Decimal(multiplicador.denominator)
                )
                assert pagos.premio(apuesta, multiplicador) <= exacto
