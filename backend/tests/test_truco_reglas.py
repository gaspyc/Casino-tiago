"""Reglas del truco: jerarquía, envido, pardas y puntaje.

Son unitarios y exhaustivos donde se puede: el mazo tiene 40 cartas y las manos
posibles son 9880, así que no hace falta muestrear nada.
"""

from collections import Counter
from itertools import combinations

import pytest

from app.modules.games.truco import reglas
from app.modules.games.truco.cartas import (
    JERARQUIA,
    MAZO,
    PALOS,
    carta_mas_alta,
    comparar,
    palo_de,
    puntos_envido,
    tantos_de_flor,
    tiene_flor,
    valor_de,
    valor_envido,
)
from app.modules.games.truco.fairness import mezclar, repartir

TODAS_LAS_MANOS = list(combinations(MAZO, 3))


# ------------------------------- el mazo -------------------------------

def test_el_mazo_tiene_cuarenta_cartas_distintas():
    assert len(MAZO) == 40
    assert len(set(MAZO)) == 40
    assert len(TODAS_LAS_MANOS) == 9880


def test_no_hay_ochos_ni_nueves():
    """El mazo español de truco va del 1 al 7 y después 10, 11 y 12."""
    assert {valor_de(carta) for carta in MAZO} == {1, 2, 3, 4, 5, 6, 7, 10, 11, 12}
    assert Counter(palo_de(carta) for carta in MAZO) == {palo: 10 for palo in PALOS}


def test_todas_las_cartas_tienen_escalon():
    assert set(JERARQUIA) == set(MAZO)


# ------------------------------- jerarquía -------------------------------

def test_el_ancho_de_espada_le_gana_a_todo():
    for carta in MAZO:
        if carta != "1E":
            assert comparar("1E", carta) == 1


def test_el_orden_de_las_cartas_bravas():
    """1E > 1B > 7E > 7O > cualquier 3."""
    assert comparar("1E", "1B") == 1
    assert comparar("1B", "7E") == 1
    assert comparar("7E", "7O") == 1
    assert comparar("7O", "3E") == 1
    assert comparar("3E", "2E") == 1


def test_el_tres_le_gana_al_dos_y_el_dos_al_ancho_falso():
    assert comparar("3C", "2O") == 1
    assert comparar("2C", "1O") == 1
    assert comparar("1O", "12E") == 1


def test_los_sietes_malos_valen_menos_que_la_sota():
    """El 7 de copa y el de basto quedan debajo de las figuras."""
    assert comparar("10E", "7C") == 1
    assert comparar("10E", "7B") == 1
    assert comparar("7C", "6E") == 1


def test_el_cuatro_pierde_contra_todo():
    for carta in MAZO:
        if valor_de(carta) != 4:
            assert comparar("4E", carta) == -1


@pytest.mark.parametrize("valor", [3, 2, 12, 11, 10, 6, 5, 4])
def test_las_cartas_del_mismo_escalon_empardan(valor):
    iguales = [carta for carta in MAZO if valor_de(carta) == valor]

    for una, otra in combinations(iguales, 2):
        assert comparar(una, otra) == 0


def test_comparar_es_antisimetrico():
    for una, otra in combinations(MAZO, 2):
        assert comparar(una, otra) == -comparar(otra, una)


def test_carta_mas_alta():
    assert carta_mas_alta(["4C", "1E", "3O"]) == "1E"
    assert carta_mas_alta(["4C", "4O", "4B"]) == "4C"  # empardan: la primera


# ------------------------------- envido -------------------------------

def _envido_de_referencia(mano) -> int:
    """Implementación independiente, para contrastar la del juego."""
    mejor = 0
    for una, otra in combinations(mano, 2):
        if palo_de(una) == palo_de(otra):
            mejor = max(mejor, valor_envido(una) + valor_envido(otra) + 20)

    if mejor:
        return mejor

    return max(valor_envido(carta) for carta in mano)


def test_el_envido_coincide_con_la_referencia_en_las_9880_manos():
    for mano in TODAS_LAS_MANOS:
        assert puntos_envido(mano) == _envido_de_referencia(mano)


def test_las_figuras_valen_cero_para_el_envido():
    assert valor_envido("12E") == 0
    assert valor_envido("11E") == 0
    assert valor_envido("10E") == 0
    assert valor_envido("7E") == 7


def test_casos_conocidos_de_envido():
    assert puntos_envido(["7E", "6E", "4C"]) == 33   # el máximo con dos del palo
    assert puntos_envido(["12E", "11E", "4C"]) == 20  # dos figuras del mismo palo
    assert puntos_envido(["12E", "11B", "10O"]) == 0  # tres figuras de distinto palo
    assert puntos_envido(["7E", "6B", "4C"]) == 7     # sin dos del mismo palo
    assert puntos_envido(["7E", "7B", "6E"]) == 33    # usa las dos de espada


def test_el_envido_nunca_pasa_de_treinta_y_tres():
    assert max(puntos_envido(mano) for mano in TODAS_LAS_MANOS) == 33


# ------------------------------- flor -------------------------------

def test_flor_es_tener_las_tres_del_mismo_palo():
    assert tiene_flor(["7E", "6E", "4E"]) is True
    assert tiene_flor(["7E", "6E", "4C"]) is False


def test_tantos_de_una_flor():
    assert tantos_de_flor(["7E", "6E", "4E"]) == 37
    assert tantos_de_flor(["12E", "11E", "10E"]) == 20


# --------------------------- quién gana la mano ---------------------------

MANO, PIE, PARDA = reglas.GANA_MANO, reglas.GANA_PIE, reglas.PARDA


@pytest.mark.parametrize(
    "resultados, esperado",
    [
        ([MANO, MANO], MANO),                  # ganó las dos primeras
        ([PIE, PIE], PIE),
        ([MANO, PARDA], MANO),                 # ganó la primera, empardó la segunda
        ([PIE, PARDA], PIE),
        ([MANO, PIE, MANO], MANO),             # una cada uno, define la tercera
        ([MANO, PIE, PIE], PIE),
        ([MANO, PIE, PARDA], MANO),            # tercera parda: manda la primera
        ([PIE, MANO, PARDA], PIE),
        ([PARDA, MANO], MANO),                 # parda la primera: define la segunda
        ([PARDA, PIE], PIE),
        ([PARDA, PARDA, MANO], MANO),          # dos pardas: define la tercera
        ([PARDA, PARDA, PIE], PIE),
        ([PARDA, PARDA, PARDA], MANO),         # todo parda: gana el mano
    ],
)
def test_ganador_de_la_mano(resultados, esperado):
    assert reglas.ganador_de_la_mano(resultados, mano=MANO) == esperado


def test_con_las_tres_pardas_gana_el_que_es_mano():
    assert reglas.ganador_de_la_mano([PARDA, PARDA, PARDA], mano=PIE) == PIE


@pytest.mark.parametrize(
    "resultados",
    [[], [MANO], [PARDA], [PARDA, PARDA], [MANO, PIE]],
)
def test_la_mano_sigue_abierta(resultados):
    assert reglas.ganador_de_la_mano(resultados, mano=MANO) is None


# ------------------------------- puntaje -------------------------------

def test_la_mano_sin_cantar_vale_uno():
    assert reglas.puntos_truco([], querido=True) == 1
    assert reglas.puntos_truco([], querido=False) == 1


@pytest.mark.parametrize(
    "cantos, querido, esperado",
    [
        (["truco"], True, 2),
        (["truco"], False, 1),
        (["truco", "retruco"], True, 3),
        (["truco", "retruco"], False, 2),
        (["truco", "retruco", "vale_cuatro"], True, 4),
        (["truco", "retruco", "vale_cuatro"], False, 3),
    ],
)
def test_puntos_del_truco(cantos, querido, esperado):
    assert reglas.puntos_truco(cantos, querido) == esperado


@pytest.mark.parametrize(
    "cantos", [["retruco"], ["truco", "vale_cuatro"], ["truco", "truco"], ["envido"]]
)
def test_el_truco_no_puede_saltear_ni_repetir(cantos):
    with pytest.raises(ValueError):
        reglas.puntos_truco(cantos, querido=True)


@pytest.mark.parametrize(
    "cantos, querido, esperado",
    [
        (["envido"], True, 2),
        (["envido"], False, 1),
        (["envido", "envido"], True, 4),
        (["envido", "envido"], False, 2),
        (["real_envido"], True, 3),
        (["real_envido"], False, 1),
        (["envido", "real_envido"], True, 5),
        (["envido", "real_envido"], False, 2),
        (["envido", "envido", "real_envido"], True, 7),
        (["envido", "envido", "real_envido"], False, 4),
    ],
)
def test_puntos_del_envido(cantos, querido, esperado):
    assert reglas.puntos_envido(cantos, querido) == esperado


def test_la_falta_envido_vale_lo_que_falta_para_salir():
    assert reglas.puntos_envido(["falta_envido"], True, puntos_a=0, puntos_b=0) == 30
    assert reglas.puntos_envido(["falta_envido"], True, puntos_a=22, puntos_b=5) == 8
    assert reglas.puntos_envido(["falta_envido"], True, puntos_a=29, puntos_b=29) == 1


def test_la_falta_no_querida_paga_lo_acumulado():
    assert reglas.puntos_envido(["falta_envido"], False) == 1
    assert reglas.puntos_envido(["envido", "falta_envido"], False) == 2


def test_con_el_mismo_envido_gana_el_mano():
    assert reglas.gana_el_envido(27, 27, jugador_es_mano=True) is True
    assert reglas.gana_el_envido(27, 27, jugador_es_mano=False) is False
    assert reglas.gana_el_envido(28, 27, jugador_es_mano=False) is True


# ------------------------------ el reparto ------------------------------

def test_el_reparto_es_deterministico():
    assert repartir("a" * 64, "cliente", 1) == repartir("a" * 64, "cliente", 1)


def test_el_reparto_usa_el_mazo_entero_sin_repetir():
    mazo = mezclar("a" * 64, "cliente", 1)

    assert sorted(mazo) == sorted(MAZO)


def test_reparte_tres_cartas_a_cada_uno_sin_repetir():
    manos = repartir("a" * 64, "cliente", 1, jugadores=2)
    repartidas = manos[0] + manos[1]

    assert len(manos) == 2
    assert all(len(mano) == 3 for mano in manos)
    assert len(set(repartidas)) == 6


def test_el_nonce_cambia_el_reparto():
    repartos = {tuple(mezclar("a" * 64, "cliente", nonce)) for nonce in range(50)}

    assert len(repartos) == 50


def test_cada_carta_sale_en_cualquier_posicion_con_la_misma_frecuencia():
    """El muestreo con rechazo evita el sesgo de tomar el byte módulo 40."""
    repeticiones = 8000
    primeras = Counter(mezclar("a" * 64, "cliente", nonce)[0] for nonce in range(repeticiones))

    esperado = repeticiones / 40
    assert len(primeras) == 40
    for carta in MAZO:
        assert abs(primeras[carta] - esperado) < esperado * 0.45
