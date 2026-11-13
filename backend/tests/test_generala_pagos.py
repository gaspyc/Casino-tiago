"""La tabla de pagos por puntaje de la generala contra la casa.

Lo que importa acá es que la casa no pueda perder: que el techo esté donde
dice estar, que sea exacto y no estimado, y que el pago salga de la fracción
y no del multiplicador redondeado.
"""

from decimal import ROUND_DOWN, Decimal

import pytest

try:
    from app.modules.games.generala import pagos
    from app.modules.games.generala.dados import PUNTAJE_SERVIDA
    from app.modules.games.generala.optimo import techo_del_pago, valor_de_la_partida
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip("No se pudo importar (%s)" % exc, allow_module_level=True)


# ------------------------------ la forma del pago ------------------------------

def test_el_equilibrio_devuelve_exactamente_la_apuesta():
    """Es la definición del número: ese puntaje no gana ni pierde."""
    assert pagos.multiplicador(pagos.PUNTAJE_DE_EQUILIBRIO) == Decimal("1.0000")
    assert pagos.premio(Decimal("100.00"), pagos.PUNTAJE_DE_EQUILIBRIO) == Decimal("100.00")


def test_cero_puntos_no_paga_nada():
    assert pagos.premio(Decimal("100.00"), 0) == Decimal("0.00")


def test_el_pago_es_proporcional_al_puntaje():
    """Sin umbral: es una recta por el origen. De eso depende el techo exacto."""
    apuesta = Decimal("100.00")

    for puntaje in (20, 50, 90, 140, 200):
        doble = pagos.premio(apuesta, puntaje * 2)
        simple = pagos.premio(apuesta, puntaje)
        assert abs(doble - simple * 2) <= Decimal("0.01")


def test_mas_puntos_nunca_paga_menos():
    anterior = Decimal("-1")
    for puntaje in range(0, 300):
        actual = pagos.premio(Decimal("50.00"), puntaje)
        assert actual >= anterior
        anterior = actual


def test_no_hay_umbral():
    """Un umbral sería un acantilado, y el casual se cae más seguido.

    Medido: con umbral 80 la brecha sube a 1,51x y con 100 a 1,70x, peor que
    el pago binario que se quería arreglar.
    """
    assert pagos.premio(Decimal("100.00"), 1) > 0
    assert pagos.premio(Decimal("100.00"), 20) > 0


def test_el_puntaje_negativo_no_pasa():
    with pytest.raises(ValueError):
        pagos.premio(Decimal("10.00"), -1)


# ------------------------------ el premio por servida ------------------------------

def test_la_servida_suma_el_premio_aparte():
    sin = pagos.multiplicador(140, servida=False)
    con = pagos.multiplicador(140, servida=True)
    assert con - sin == pagos.PREMIO_SERVIDA


def test_la_servida_se_paga_sobre_la_apuesta():
    apuesta = Decimal("20.00")
    diferencia = pagos.premio(apuesta, 140, True) - pagos.premio(apuesta, 140, False)
    assert diferencia == apuesta * pagos.PREMIO_SERVIDA


# ------------------------------ el redondeo ------------------------------

def test_el_premio_sale_de_la_fraccion_y_no_del_multiplicador():
    """Truncar el multiplicador y después multiplicar se come RTP.

    En el mines esa diferencia fueron 0,7 puntos de RTP. Acá se verifica que
    el pago use la fracción exacta: el multiplicador mostrado está truncado a
    cuatro decimales, así que multiplicarlo da de menos.
    """
    apuesta = Decimal("1000.00")
    puntaje = 137

    por_el_mostrado = (pagos.multiplicador(puntaje) * apuesta).quantize(Decimal("0.01"))
    exacto = pagos.premio(apuesta, puntaje)

    assert exacto >= por_el_mostrado
    # Y la fraccion da lo correcto, truncando (nunca pagar de mas) y sin
    # pasar por el multiplicador mostrado.
    assert exacto == (apuesta * puntaje / pagos.PUNTAJE_DE_EQUILIBRIO).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )


def test_el_pago_nunca_se_redondea_para_arriba():
    """Redondear para arriba le regalaría centavos a la casa en contra."""
    for puntaje in range(1, 260, 7):
        for apuesta in (Decimal("0.01"), Decimal("3.33"), Decimal("97.77")):
            exacto = Decimal(apuesta) * puntaje / pagos.PUNTAJE_DE_EQUILIBRIO
            assert pagos.premio(apuesta, puntaje) <= exacto


# ------------------------------ el techo ------------------------------

def test_el_techo_esta_abajo_del_objetivo():
    """La casa no puede perder ni contra el que juega perfecto."""
    techo = techo_del_pago(
        0.0, 1.0 / pagos.PUNTAJE_DE_EQUILIBRIO, float(pagos.PREMIO_SERVIDA)
    )

    assert techo <= float(pagos.RTP_OBJETIVO), techo
    # Y tampoco tan abajo que la ventaja de la casa sea abusiva.
    assert techo > 0.93, techo


def test_el_techo_es_exacto_y_no_estimado():
    """La política que yo había programado a mano queda 6% abajo del óptimo.

    Calibrar con ella habría puesto al jugador perfecto arriba del 100% y la
    casa pierde plata con cada partida. Este test fija esa brecha para que no
    se pierda de vista.
    """
    optimo = valor_de_la_partida()
    mejor_heuristica = 140.0  # medido, `simular.py pagos`

    assert optimo > mejor_heuristica * 1.05

    # Lo que habria pasado calibrando con la heuristica.
    equilibrio_mal = mejor_heuristica / float(pagos.RTP_OBJETIVO)
    rtp_del_perfecto = optimo / equilibrio_mal
    assert rtp_del_perfecto > 1.0, rtp_del_perfecto


def test_el_premio_por_servida_entra_en_el_techo():
    """Con premio el juego perfecto cambia: cuida la fila de la generala.

    Si el techo se calculara sin eso, quedaría corto y la casa con menos
    ventaja de la que cree.
    """
    a = 1.0 / pagos.PUNTAJE_DE_EQUILIBRIO

    con_premio = techo_del_pago(0.0, a, float(pagos.PREMIO_SERVIDA))
    ignorando = a * valor_de_la_partida(0.0) + float(pagos.PREMIO_SERVIDA) * 0.0055

    assert con_premio > ignorando


def test_la_servida_vale_lo_que_dice_la_regla():
    """El premio se cobra por anotar la generala servida, que son 60 puntos."""
    assert PUNTAJE_SERVIDA["generala"] == 60


# ------------------------------ la tabla de referencia ------------------------------

def test_la_tabla_de_referencia_incluye_el_equilibrio():
    tabla = pagos.tabla_de_referencia()
    puntajes = [fila["puntaje"] for fila in tabla]

    assert pagos.PUNTAJE_DE_EQUILIBRIO in puntajes
    assert puntajes == sorted(puntajes)

    for fila in tabla:
        assert Decimal(fila["multiplicador"]) == pagos.multiplicador(fila["puntaje"])
