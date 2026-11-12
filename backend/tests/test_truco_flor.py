"""La flor, que es opcional y cambia cómo se juega la primera mano.

La flor tiene variantes regionales. Ésta es la que juega el casino:
- La flor vale 3 y no se puede rechazar: si el rival no tiene flor, se cobra.
- Si los dos tienen, el segundo sube a contraflor (6) o dice que son buenas.
- Lo no querido paga lo que valía el canto anterior.
- La flor mata al envido: cuando hay flor, el envido no se juega.
"""

import pytest

from app.modules.games.truco import reglas
from app.modules.games.truco.mano import AccionInvalida, Mano, NO_QUIERO, QUIERO

FLOR_ALTA = ["7E", "6E", "4E"]    # 37 de flor
FLOR_BAJA = ["12B", "11B", "10B"]  # 20 de flor
SIN_FLOR = ["3B", "6C", "7O"]
OTRA_SIN_FLOR = ["4C", "5B", "6O"]


def _mano(cartas_0, cartas_1, mano=0, con_flor=True, puntos=(0, 0)):
    return Mano([cartas_0, cartas_1], mano=mano, puntos_partida=puntos, con_flor=con_flor)


# ------------------------------ opcional ------------------------------

def test_sin_la_opcion_prendida_no_hay_flor():
    partida = _mano(FLOR_ALTA, SIN_FLOR, con_flor=False)

    assert "flor" not in partida.acciones(0)
    assert partida.tiene_flor(0) is False


def test_con_la_opcion_prendida_el_que_la_tiene_puede_cantarla():
    partida = _mano(FLOR_ALTA, SIN_FLOR)

    assert "flor" in partida.acciones(0)
    assert partida.tiene_flor(0) is True


def test_el_que_no_tiene_flor_no_la_puede_cantar():
    partida = _mano(SIN_FLOR, FLOR_ALTA)

    assert "flor" not in partida.acciones(0)
    with pytest.raises(AccionInvalida):
        partida.cantar(0, "flor")


# --------------------------- la flor mata al envido ---------------------------

def test_el_que_tiene_flor_no_canta_envido():
    partida = _mano(FLOR_ALTA, SIN_FLOR)

    assert "envido" not in partida.acciones(0)
    assert "real_envido" not in partida.acciones(0)


def test_la_flor_tapa_un_envido_cantado():
    """El rival canta envido y el de la flor la canta encima: el envido muere."""
    partida = _mano(FLOR_ALTA, SIN_FLOR, mano=1)

    partida.jugar(1, "3B")
    partida.cantar(0, "flor")

    assert partida.puntos == [3, 0]
    assert partida.envido_resuelto is True
    assert partida.cantos_envido == []


def test_el_envido_del_rival_se_contesta_con_flor():
    partida = _mano(SIN_FLOR, FLOR_ALTA)

    partida.cantar(0, "envido")

    assert partida.acciones(1) == ["flor"]

    partida.cantar(1, "flor")

    assert partida.puntos == [0, 3]      # cobra la flor
    assert partida.envido_resuelto is True
    assert partida.pendiente is None


def test_despues_de_la_flor_no_se_canta_envido():
    partida = _mano(FLOR_ALTA, SIN_FLOR)

    partida.cantar(0, "flor")

    assert "envido" not in partida.acciones(0)
    assert "envido" not in partida.acciones(1)


# ------------------------------ una sola flor ------------------------------

def test_la_flor_sola_se_cobra_sin_preguntar():
    partida = _mano(FLOR_ALTA, SIN_FLOR)

    partida.cantar(0, "flor")

    assert partida.puntos == [3, 0]
    assert partida.pendiente is None
    assert partida.flor_resuelta is True
    assert partida.terminada is False  # la mano sigue


def test_no_se_canta_flor_dos_veces():
    partida = _mano(FLOR_ALTA, SIN_FLOR)

    partida.cantar(0, "flor")

    assert "flor" not in partida.acciones(0)


def test_la_flor_es_solo_en_la_primera():
    partida = _mano(FLOR_ALTA, SIN_FLOR)

    partida.jugar(0, "4E")
    partida.jugar(1, "3B")

    assert "flor" not in partida.acciones(1)
    assert "flor" not in partida.acciones(0)


# ------------------------------ dos flores ------------------------------

def test_con_dos_flores_el_rival_sube_o_se_achica():
    partida = _mano(FLOR_ALTA, FLOR_BAJA)

    partida.cantar(0, "flor")

    assert set(partida.acciones(1)) == {"contraflor", "contraflor_al_resto", NO_QUIERO}
    assert QUIERO not in partida.acciones(1)


def test_son_buenas_le_paga_tres_al_que_canto():
    partida = _mano(FLOR_ALTA, FLOR_BAJA)

    partida.cantar(0, "flor")
    partida.responder(1, NO_QUIERO)

    assert partida.puntos == [3, 0]


def test_la_contraflor_querida_la_gana_la_flor_mas_alta():
    partida = _mano(FLOR_ALTA, FLOR_BAJA)

    partida.cantar(0, "flor")
    partida.cantar(1, "contraflor")
    partida.responder(0, QUIERO)

    assert partida.puntos == [6, 0]  # 37 contra 20


def test_la_contraflor_no_querida_paga_lo_que_valia_la_flor():
    partida = _mano(FLOR_ALTA, FLOR_BAJA)

    partida.cantar(0, "flor")
    partida.cantar(1, "contraflor")
    partida.responder(0, NO_QUIERO)

    assert partida.puntos == [0, 3]


def test_la_contraflor_al_resto_vale_lo_que_falta():
    partida = _mano(FLOR_ALTA, FLOR_BAJA, puntos=(21, 8))

    partida.cantar(0, "flor")
    partida.cantar(1, "contraflor_al_resto")
    partida.responder(0, QUIERO)

    assert partida.puntos == [9, 0]  # 30 - 21, y la gana la flor más alta


def test_con_la_misma_flor_gana_el_mano():
    iguales = ["7E", "6E", "4E"]
    otras = ["7O", "6O", "4O"]  # también 37
    partida = _mano(iguales, otras, mano=1)

    partida.jugar(1, "4O")
    partida.cantar(0, "flor")
    partida.cantar(1, "contraflor")
    partida.responder(0, QUIERO)

    assert partida.puntos == [0, 6]


# ------------------------------ puntaje suelto ------------------------------

@pytest.mark.parametrize(
    "cantos, querido, esperado",
    [
        (["flor"], False, 3),
        (["flor"], True, 3),
        (["flor", "contraflor"], True, 6),
        (["flor", "contraflor"], False, 3),
        (["flor", "contraflor", "contraflor_al_resto"], False, 6),
    ],
)
def test_puntos_de_los_cantos_de_flor(cantos, querido, esperado):
    assert reglas.puntos_flor(cantos, querido) == esperado


def test_la_contraflor_al_resto_querida_es_la_falta():
    assert reglas.puntos_flor(["flor", "contraflor_al_resto"], True, 25, 10) == 5


def test_un_canto_que_no_es_de_flor_es_un_error():
    with pytest.raises(ValueError):
        reglas.puntos_flor(["envido"], True)


# ------------------------------ el bot ------------------------------

def test_el_bot_canta_la_flor_que_le_toca():
    from app.modules.games.truco import bot

    partida = _mano(FLOR_ALTA, SIN_FLOR)

    assert bot.decidir(partida, 0) == "flor"


def test_el_bot_tapa_el_envido_con_la_flor():
    from app.modules.games.truco import bot

    partida = _mano(SIN_FLOR, FLOR_ALTA)
    partida.cantar(0, "envido")

    assert bot.decidir(partida, 1) == "flor"


def test_el_bot_sube_a_contraflor_con_flor_alta():
    from app.modules.games.truco import bot

    partida = _mano(FLOR_BAJA, FLOR_ALTA)
    partida.cantar(0, "flor")

    assert bot.decidir(partida, 1) == "contraflor"


def test_el_bot_se_achica_con_flor_baja():
    from app.modules.games.truco import bot

    partida = _mano(FLOR_ALTA, FLOR_BAJA)
    partida.cantar(0, "flor")

    assert bot.decidir(partida, 1) == NO_QUIERO


def test_una_partida_con_flor_entre_bots_termina():
    from app.modules.games.truco import bot
    from app.modules.games.truco.mano import aplicar_accion, jugador_en_turno
    from app.modules.games.truco.partida import Partida

    for semilla in range(8):
        partida = Partida("a" * 64, "flor-%d" % semilla, 0, con_flor=True)
        pasos = 0

        while not partida.terminada:
            mano = partida.nueva_mano()
            while not mano.terminada:
                pasos += 1
                assert pasos < 900, "la partida con flor no termina"
                jugador = jugador_en_turno(mano)
                accion = bot.decidir(mano, jugador)
                assert accion in mano.acciones(jugador)
                aplicar_accion(mano, jugador, accion)
            partida.cerrar_mano()

        assert partida.ganador in (0, 1)


def test_la_flor_no_dice_nada_sobre_la_fuerza_de_las_cartas():
    """Se puede tener flor con 4, 5 y 6: el palo no habla del poder."""
    from itertools import combinations

    from app.modules.games.truco import bot
    from app.modules.games.truco.cartas import MAZO, tiene_flor

    manos = list(combinations(MAZO, 3))
    con = [m for m in manos if tiene_flor(m)]
    sin = [m for m in manos if not tiene_flor(m)]

    media = lambda grupo: sum(bot.fuerza_de_mano(list(m)) for m in grupo) / len(grupo)

    assert len(con) == 480  # 4.86% de las manos
    assert abs(media(con) - media(sin)) < 0.001


def test_la_flor_suma_confianza_para_el_truco_sin_tocar_las_cartas():
    """Lo que cambia no son las cartas sino lo que cuesta perder."""
    from app.modules.games.truco import bot

    con_flor = _mano(["12E", "11E", "10E"], SIN_FLOR)
    sin_flor = _mano(["12E", "11B", "10C"], SIN_FLOR)

    assert bot.fuerza_de_mano(con_flor.cartas[0]) == bot.fuerza_de_mano(sin_flor.cartas[0])
    assert bot._fuerza_en_juego(con_flor, 0) == pytest.approx(
        bot._fuerza_en_juego(sin_flor, 0) + bot.BONIFICACION_POR_FLOR
    )


def test_con_la_flor_cobrada_se_anima_a_cantar_truco():
    """Con esas mismas cartas, sin flor no cantaría."""
    from app.modules.games.truco import bot

    con_flor = _mano(["12E", "11E", "10E"], SIN_FLOR)
    con_flor.cantar(0, "flor")  # el rival no tiene: se cobra y sigue la mano

    sin_flor = _mano(["12E", "11B", "10C"], SIN_FLOR)

    assert con_flor.puntos == [3, 0]
    assert bot.decidir(con_flor, 0) == "truco"
    assert bot.decidir(sin_flor, 0) != "truco"
