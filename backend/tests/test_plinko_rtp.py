"""RTP y geometría de Plinko.

Importan el servicio (que arrastra sqlalchemy), así que corren dentro del
contenedor. No tocan la base.
"""

from math import comb

import pytest

try:
    from app.modules.games.plinko.fairness import derivar_camino, slot_desde_camino
    from app.modules.games.plinko.service import (
        BOARD_CENTER_X,
        RISK_CONFIG,
        TARGET_RTP,
        build_board_map,
        build_multipliers,
        construir_tiro,
        get_col_gap,
        get_pegs,
        get_slot_x,
    )
except Exception as exc:  # pragma: no cover - entorno sin sqlalchemy
    pytest.skip(
        "Requiere las dependencias del backend, correr dentro de Docker (%s)" % exc,
        allow_module_level=True,
    )

RIESGOS = sorted(RISK_CONFIG)
FILAS_POSIBLES = range(8, 17)  # lo que permite el schema


def _rtp(filas: int, riesgo: str) -> float:
    """Devuelto esperado por unidad apostada, sobre la distribución binomial.

    No hace falta simular: el camino sale de un HMAC con una decisión por fila,
    así que la probabilidad de cada slot es exactamente C(filas, slot) / 2^filas.
    """
    multiplicadores = build_multipliers(filas, riesgo)
    return sum(
        comb(filas, slot) / (2 ** filas) * float(multiplicadores[slot])
        for slot in range(filas + 1)
    )


# ------------------------------- RTP -------------------------------

@pytest.mark.parametrize("filas", FILAS_POSIBLES)
@pytest.mark.parametrize("riesgo", RIESGOS)
def test_rtp_cerca_del_objetivo(filas, riesgo):
    """El RTP se normaliza a 96% y lo único que lo corre es el redondeo."""
    assert abs(_rtp(filas, riesgo) - TARGET_RTP) < 0.005


@pytest.mark.parametrize("filas", FILAS_POSIBLES)
@pytest.mark.parametrize("riesgo", RIESGOS)
def test_la_casa_nunca_paga_mas_de_lo_que_cobra(filas, riesgo):
    """Regresión de lo que hacía la simulación física.

    El clamp de los bordes metía en los slots extremos (los de mayor
    multiplicador) toda bola que se pasaba de rango. Medido sobre 40.000 tiros
    de 12 filas, el RTP real era 99.5% en riesgo bajo, 110% en medio y 177% en
    alto: la casa perdía plata en cada tiro.
    """
    assert _rtp(filas, riesgo) < 1.0


@pytest.mark.parametrize("filas", FILAS_POSIBLES)
def test_hay_un_multiplicador_por_slot(filas):
    for riesgo in RIESGOS:
        assert len(build_multipliers(filas, riesgo)) == filas + 1


def test_mas_riesgo_es_mas_premio_en_los_extremos():
    multiplicadores = {riesgo: build_multipliers(12, riesgo) for riesgo in RIESGOS}

    assert multiplicadores["high"][0] > multiplicadores["medium"][0]
    assert multiplicadores["medium"][0] > multiplicadores["low"][0]
    # Y menos premio en el centro, que es donde cae la mayoría de las bolas.
    assert multiplicadores["high"][6] < multiplicadores["low"][6]


# ------------------------------- geometría -------------------------------

@pytest.mark.parametrize("filas", FILAS_POSIBLES)
def test_pines_y_slots_comparten_el_espaciado(filas):
    """El bug que se arrastraba: dos espaciados distintos en el mismo tablero.

    Antes los pines usaban un COL_GAP fijo de 46 y los slots BOARD_WIDTH/(filas+1),
    así que la bola caía en un lugar y se iluminaba otro slot.
    """
    gap = get_col_gap(filas)

    centros = [get_slot_x(slot, filas) for slot in range(filas + 1)]
    for anterior, siguiente in zip(centros, centros[1:]):
        assert abs((siguiente - anterior) - gap) < 1e-9

    # La última fila de pines tiene un pin por cada hueco entre slots.
    ultima_fila = [x for x, y in get_pegs(filas) if y == max(y for _, y in get_pegs(filas))]
    for anterior, siguiente in zip(ultima_fila, ultima_fila[1:]):
        assert abs((siguiente - anterior) - gap) < 1e-9


@pytest.mark.parametrize("filas", FILAS_POSIBLES)
def test_el_tablero_esta_centrado(filas):
    primero = get_slot_x(0, filas)
    ultimo = get_slot_x(filas, filas)

    assert abs((primero + ultimo) / 2 - BOARD_CENTER_X) < 1e-9


@pytest.mark.parametrize("filas", FILAS_POSIBLES)
def test_el_tablero_depende_solo_de_las_filas(filas):
    """El riesgo cambia los multiplicadores, nunca la geometría."""
    assert build_board_map(filas) == build_board_map(filas)
    assert len(build_board_map(filas)["slots"]) == filas + 1
    assert len(build_board_map(filas)["pegs"]) == filas * (filas + 1) // 2


# ------------------------------- animación -------------------------------

@pytest.mark.parametrize("filas", FILAS_POSIBLES)
def test_la_animacion_sigue_el_camino_del_seed(filas):
    camino = derivar_camino("a" * 64, "cliente", 1, filas)

    tiro = construir_tiro(filas, camino)

    assert tiro["path"] == camino
    assert tiro["slot_index"] == slot_desde_camino(camino)


@pytest.mark.parametrize("filas", FILAS_POSIBLES)
def test_la_bola_termina_en_el_centro_de_su_slot(filas):
    """Cierra el círculo entre el resultado y lo que se ve en pantalla."""
    camino = derivar_camino("a" * 64, "cliente", 7, filas)
    tiro = construir_tiro(filas, camino)

    ultimo = tiro["visual_path"][-1]

    assert abs(ultimo["x"] - get_slot_x(tiro["slot_index"], filas)) < 1.0


def test_un_camino_de_otro_tablero_es_un_error():
    """Era la forma en que se desalineaba todo: geometría de otras filas."""
    camino = derivar_camino("a" * 64, "cliente", 1, 12)

    with pytest.raises(ValueError):
        construir_tiro(16, camino)
