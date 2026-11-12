"""La máquina de estados de una mano de truco.

Las manos se arman a mano (valga) para que cada test tenga un reparto
conocido: el jugador 0 es el mano y juega primero.
"""

import pytest

from app.modules.games.truco.mano import AccionInvalida, Mano, NO_QUIERO, QUIERO
from app.modules.games.truco.reglas import PARDA


def _mano(cartas_0, cartas_1, mano=0, puntos=(0, 0)):
    return Mano([cartas_0, cartas_1], mano=mano, puntos_partida=puntos)


# ------------------------------ el reparto ------------------------------

def test_arranca_jugando_el_mano():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    assert partida.turno == 0
    assert "jugar:1E" in partida.acciones(0)
    assert partida.acciones(1) == []


def test_el_pie_no_puede_jugar_fuera_de_turno():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    with pytest.raises(AccionInvalida):
        partida.jugar(1, "3B")


def test_no_se_puede_jugar_una_carta_que_no_se_tiene():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    with pytest.raises(AccionInvalida):
        partida.jugar(0, "12O")


def test_hay_que_repartir_tres_cartas_a_cada_uno():
    with pytest.raises(ValueError):
        Mano([["1E", "4C"], ["3B", "6C", "7B"]])


# ------------------------------ las rondas ------------------------------

def test_la_ronda_la_gana_la_carta_mas_alta_y_el_ganador_sale():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    partida.jugar(0, "4C")
    partida.jugar(1, "3B")

    assert partida.resultados == [1]
    assert partida.turno == 1


def test_la_ronda_empardada_la_vuelve_a_salir_el_que_salio():
    partida = _mano(["3E", "4C", "5O"], ["3B", "6C", "7B"])

    partida.jugar(0, "3E")
    partida.jugar(1, "3B")

    assert partida.resultados == [PARDA]
    assert partida.turno == 0


def test_gana_la_mano_el_que_se_lleva_dos_rondas():
    partida = _mano(["1E", "1B", "4O"], ["3B", "6C", "7B"])

    partida.jugar(0, "1E")
    partida.jugar(1, "3B")
    partida.jugar(0, "1B")
    partida.jugar(1, "7B")

    assert partida.terminada is True
    assert partida.ganador == 0
    assert partida.puntos == [1, 0]  # sin cantar nada, la mano vale 1


def test_la_mano_se_define_en_la_tercera():
    partida = _mano(["1E", "4C", "2O"], ["3B", "6C", "7B"])

    partida.jugar(0, "1E")
    partida.jugar(1, "3B")      # gana 0
    partida.jugar(0, "4C")
    partida.jugar(1, "6C")      # gana 1
    partida.jugar(1, "7B")
    partida.jugar(0, "2O")      # gana 0

    assert partida.ganador == 0
    assert partida.puntos == [1, 0]


# ------------------------------ el truco ------------------------------

def test_el_truco_no_querido_paga_uno():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    partida.cantar(0, "truco")
    partida.responder(1, NO_QUIERO)

    assert partida.terminada is True
    assert partida.ganador == 0
    assert partida.puntos == [1, 0]


def test_el_truco_querido_hace_valer_dos_la_mano():
    partida = _mano(["1E", "1B", "4O"], ["3B", "6C", "7B"])

    partida.cantar(0, "truco")
    partida.responder(1, QUIERO)
    partida.jugar(0, "1E")
    partida.jugar(1, "3B")
    partida.jugar(0, "1B")
    partida.jugar(1, "7B")

    assert partida.puntos == [2, 0]


def test_el_retruco_no_querido_paga_dos():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    partida.cantar(0, "truco")
    partida.cantar(1, "retruco")
    partida.responder(0, NO_QUIERO)

    assert partida.ganador == 1
    assert partida.puntos == [0, 2]


def test_la_escalera_del_truco_llega_hasta_vale_cuatro():
    partida = _mano(["1E", "1B", "4O"], ["3B", "6C", "7B"])

    partida.cantar(0, "truco")
    partida.cantar(1, "retruco")
    partida.cantar(0, "vale_cuatro")
    partida.responder(1, QUIERO)

    assert partida.acciones(0) == [] or "vale_cuatro" not in partida.acciones(0)

    partida.jugar(0, "1E")
    partida.jugar(1, "3B")
    partida.jugar(0, "1B")
    partida.jugar(1, "7B")

    assert partida.puntos == [4, 0]


def test_no_se_puede_recantar_sin_que_el_rival_conteste():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    partida.cantar(0, "truco")

    with pytest.raises(AccionInvalida):
        partida.cantar(0, "retruco")


def test_el_que_canto_no_puede_contestarse_solo():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    partida.cantar(0, "truco")

    assert partida.acciones(0) == []
    with pytest.raises(AccionInvalida):
        partida.responder(0, QUIERO)


def test_irse_al_mazo_le_da_al_rival_lo_que_valia_la_mano():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    partida.cantar(0, "truco")
    partida.responder(1, QUIERO)
    partida.jugar(0, "1E")
    partida.irse_al_mazo(1)

    assert partida.ganador == 0
    assert partida.puntos == [2, 0]


# ------------------------------ el envido ------------------------------

def test_el_envido_no_querido_paga_uno():
    partida = _mano(["7E", "6E", "4C"], ["3B", "6C", "7B"])

    partida.cantar(0, "envido")
    partida.responder(1, NO_QUIERO)

    assert partida.puntos == [1, 0]
    assert partida.terminada is False  # la mano sigue


def test_el_envido_querido_lo_gana_el_que_tiene_mas_tantos():
    partida = _mano(["7E", "6E", "4C"], ["3B", "6C", "7B"])  # 33 contra 6

    partida.jugar(0, "4C")        # habla primero el mano
    partida.cantar(1, "envido")
    partida.responder(0, QUIERO)

    assert partida.puntos == [2, 0]


def test_con_tantos_iguales_gana_el_mano():
    partida = _mano(["7E", "6E", "4C"], ["7O", "6O", "4B"], mano=1)  # 33 y 33

    partida.jugar(1, "4B")        # el mano es el jugador 1
    partida.cantar(0, "envido")
    partida.responder(1, QUIERO)

    assert partida.puntos == [0, 2]


def test_el_envido_se_puede_subir():
    partida = _mano(["7E", "6E", "4C"], ["3B", "6C", "7B"])

    partida.cantar(0, "envido")
    partida.cantar(1, "real_envido")
    partida.responder(0, QUIERO)

    assert partida.puntos == [5, 0]


def test_la_falta_envido_vale_lo_que_falta_para_salir():
    partida = _mano(["7E", "6E", "4C"], ["3B", "6C", "7B"], puntos=(22, 5))

    partida.cantar(0, "falta_envido")
    partida.responder(1, QUIERO)

    assert partida.puntos == [8, 0]


def test_el_envido_solo_se_canta_en_la_primera():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    partida.jugar(0, "4C")
    partida.jugar(1, "3B")

    assert "envido" not in partida.acciones(1)
    with pytest.raises(AccionInvalida):
        partida.cantar(1, "envido")


def test_el_envido_no_se_puede_cantar_dos_veces():
    partida = _mano(["7E", "6E", "4C"], ["3B", "6C", "7B"])

    partida.cantar(0, "envido")
    partida.responder(1, QUIERO)

    assert "envido" not in partida.acciones(0)


def test_los_tantos_cuentan_las_cartas_ya_jugadas():
    """Se canta envido después de jugar la primera carta: cuentan las tres."""
    partida = _mano(["7E", "6E", "4C"], ["3B", "6C", "7B"])

    partida.jugar(0, "7E")
    partida.cantar(1, "envido")
    partida.responder(0, QUIERO)

    assert partida.puntos == [2, 0]  # el 33 del jugador 0 sigue contando


def test_el_envido_esta_primero():
    """Sobre un truco de la primera ronda se puede meter envido."""
    partida = _mano(["7E", "6E", "4C"], ["3B", "6C", "7B"])

    partida.cantar(0, "truco")

    assert "envido" in partida.acciones(1)

    partida.cantar(1, "envido")
    partida.responder(0, QUIERO)

    assert partida.puntos == [2, 0]      # el envido se resolvió
    assert partida.pendiente is None
    assert partida.terminada is False


def test_despues_de_la_primera_el_truco_no_admite_envido():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    partida.jugar(0, "4C")
    partida.jugar(1, "3B")
    partida.cantar(1, "truco")

    assert "envido" not in partida.acciones(0)


# ------------------------------ el estado ------------------------------

def test_el_estado_no_muestra_las_cartas_del_rival():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    estado = partida.estado(para=0)

    assert estado["cartas"] == ["1E", "4C", "5O"]
    assert estado["cartas_del_rival"] == 3
    assert "3B" not in str(estado)


def test_el_estado_trae_las_acciones_del_jugador():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    assert "truco" in partida.estado(para=0)["acciones"]
    assert partida.estado(para=1)["acciones"] == []


def test_el_pie_no_habla_antes_que_el_mano():
    """El mano tiene la palabra: el pie recién canta cuando le toca."""
    partida = _mano(["7E", "6E", "4C"], ["3B", "6C", "7B"])

    assert partida.acciones(1) == []
    with pytest.raises(AccionInvalida):
        partida.cantar(1, "envido")


def test_al_mazo_se_va_el_que_tiene_el_turno():
    partida = _mano(["1E", "4C", "5O"], ["3B", "6C", "7B"])

    with pytest.raises(AccionInvalida):
        partida.irse_al_mazo(1)
