"""La partida encadenada y el bot de la casa."""

import pytest

from app.modules.games.shared import rng
from app.modules.games.truco import bot
from app.modules.games.truco.cartas import JERARQUIA
from app.modules.games.truco.mano import (
    Mano,
    NO_QUIERO,
    QUIERO,
    aplicar_accion,
    jugador_en_turno,
)
from app.modules.games.truco.partida import Partida

SEED = "a" * 64


def _partida(objetivo=30, mano_inicial=0):
    return Partida(SEED, "cliente", 0, mano_inicial=mano_inicial, objetivo=objetivo)


def _al_azar(mano, jugador):
    acciones = mano.acciones(jugador)
    return rng.choice(acciones) if acciones else None


def _jugar_partida(estrategias, objetivo=30, limite=600):
    partida = Partida(SEED, "cliente-%s" % rng.uniform(0, 1), 0, objetivo=objetivo)
    pasos = 0

    while not partida.terminada:
        mano = partida.nueva_mano()
        while not mano.terminada:
            pasos += 1
            if pasos > limite:
                raise AssertionError("la mano no termina: posible bucle")

            jugador = jugador_en_turno(mano)
            accion = estrategias[jugador](mano, jugador)
            assert accion is not None, "la estrategia no devolvió acción con el turno"
            aplicar_accion(mano, jugador, accion)

        partida.cerrar_mano()

    return partida


# ------------------------------ la partida ------------------------------

def test_reparte_tres_cartas_a_cada_uno():
    partida = _partida()

    mano = partida.nueva_mano()

    assert len(mano.cartas[0]) == 3
    assert len(mano.cartas[1]) == 3
    assert len(set(mano.cartas[0] + mano.cartas[1])) == 6


def test_el_ser_mano_se_alterna():
    partida = _partida()

    assert partida.nueva_mano().mano == 0
    partida.mano_actual.irse_al_mazo(0)
    partida.cerrar_mano()

    assert partida.nueva_mano().mano == 1


def test_cada_mano_se_reparte_distinto():
    partida = _partida()
    repartos = []

    for _ in range(5):
        mano = partida.nueva_mano()
        repartos.append(tuple(mano.cartas[0] + mano.cartas[1]))
        mano.irse_al_mazo(mano.turno)
        partida.cerrar_mano()

    assert len(set(repartos)) == 5


def test_no_se_reparte_con_la_mano_abierta():
    partida = _partida()
    partida.nueva_mano()

    with pytest.raises(RuntimeError):
        partida.nueva_mano()


def test_no_se_cierra_una_mano_que_sigue():
    partida = _partida()
    partida.nueva_mano()

    with pytest.raises(RuntimeError):
        partida.cerrar_mano()


def test_la_partida_suma_los_puntos_de_cada_mano():
    partida = _partida()

    mano = partida.nueva_mano()
    mano.cantar(0, "truco")
    mano.responder(1, NO_QUIERO)
    partida.cerrar_mano()

    assert partida.puntos == [1, 0]
    assert partida.terminada is False


def test_la_partida_termina_al_llegar_al_objetivo():
    partida = _partida(objetivo=2)

    mano = partida.nueva_mano()
    mano.cantar(0, "truco")
    mano.responder(1, QUIERO)
    mano.jugar(0, mano.cartas[0][0])
    mano.irse_al_mazo(1)
    partida.cerrar_mano()

    assert partida.puntos == [2, 0]
    assert partida.terminada is True
    assert partida.ganador == 0


def test_no_se_sigue_jugando_una_partida_terminada():
    partida = _partida(objetivo=1)
    mano = partida.nueva_mano()
    mano.irse_al_mazo(0)
    partida.cerrar_mano()

    with pytest.raises(RuntimeError):
        partida.nueva_mano()


def test_el_estado_de_la_partida_oculta_las_cartas_del_rival():
    partida = _partida()
    mano = partida.nueva_mano()

    estado = partida.estado(para=0)

    assert estado["mano"]["cartas"] == mano.cartas[0]
    assert estado["mano"]["cartas_del_rival"] == 3


# ------------------------------ el bot ------------------------------

def test_el_bot_siempre_devuelve_una_accion_permitida():
    for semilla in range(40):
        partida = Partida(SEED, "cliente-%d" % semilla, 0)
        mano = partida.nueva_mano()

        pasos = 0
        while not mano.terminada:
            pasos += 1
            assert pasos < 200, "la mano no termina"

            jugador = jugador_en_turno(mano)
            accion = bot.decidir(mano, jugador)

            assert accion in mano.acciones(jugador)
            aplicar_accion(mano, jugador, accion)


def test_el_bot_canta_envido_con_buenos_tantos():
    mano = Mano([["7E", "6E", "4C"], ["3B", "6C", "7B"]], mano=0)  # 33 tantos

    assert bot.decidir(mano, 0) == "envido"


def test_el_bot_no_canta_envido_con_tantos_flojos():
    mano = Mano([["4C", "5B", "6O"], ["3B", "6C", "7B"]], mano=0)  # 6 tantos

    assert bot.decidir(mano, 0) != "envido"


def test_el_bot_no_quiere_el_envido_con_tantos_flojos():
    """4C 5B 6O son tres palos distintos: 6 tantos."""
    mano = Mano([["4C", "5B", "6O"], ["3B", "6C", "7B"]], mano=0)
    mano.jugar(0, "4C")
    mano.cantar(1, "envido")

    assert bot.decidir(mano, 0) == NO_QUIERO


def test_el_bot_quiere_el_envido_con_tantos_buenos():
    """7E y 10E son 27: alcanza para querer pero no para subir."""
    mano = Mano([["7E", "10E", "4C"], ["3B", "6C", "7B"]], mano=0)
    mano.jugar(0, "4C")
    mano.cantar(1, "envido")

    assert bot.decidir(mano, 0) == QUIERO


def test_el_bot_sube_el_envido_con_tantos_altos():
    """Con 33 no conviene aceptar: conviene cobrar mas."""
    mano = Mano([["7E", "6E", "4C"], ["3B", "6C", "7B"]], mano=0)
    mano.jugar(0, "4C")
    mano.cantar(1, "envido")

    assert bot.decidir(mano, 0) == "real_envido"


def test_el_bot_tira_la_mas_barata_que_gana():
    """Con 1E y 11B contra un 10O, el 11B alcanza: el ancho se guarda."""
    mano = Mano([["3B", "4C", "5O"], ["1E", "11B", "4O"]], mano=0)
    mano.jugar(0, "3B")

    accion = bot.decidir(mano, 1)

    assert accion in ("jugar:1E", "truco", "retruco")  # puede cantar primero
    if accion.startswith("jugar:"):
        assert accion == "jugar:1E"  # el 11B no le gana al 3


def test_el_bot_no_malgasta_cartas_cuando_no_puede_ganar():
    """Contra el ancho de espada tira la peor que tenga."""
    mano = Mano([["1E", "4C", "5O"], ["11B", "6C", "4O"]], mano=0)
    mano.jugar(0, "1E")

    accion = bot.decidir(mano, 1)

    if accion.startswith("jugar:"):
        carta = accion.split(":", 1)[1]
        assert JERARQUIA[carta] == max(JERARQUIA[c] for c in mano.cartas[1])


# --------------------------- partidas completas ---------------------------

def test_una_partida_entre_bots_siempre_termina():
    for _ in range(15):
        partida = _jugar_partida([bot.decidir, bot.decidir])

        assert partida.terminada is True
        assert partida.ganador in (0, 1)
        assert max(partida.puntos) >= partida.objetivo


def test_el_bot_le_gana_al_azar():
    """Piso de competencia: si no le gana al azar, no sirve para la casa.

    El azar de `_al_azar` sale del CSPRNG del sistema, que no se siembra, así
    que la proporción medida cambia en cada corrida. El bot gana ~90% y el
    umbral está en 80%: con 40 partidas el desvío de la proporción es de ~4,6
    puntos, el umbral queda a poco más de dos sigmas y el test falla por ruido
    una corrida de cada treinta. Con 300 el desvío baja a ~1,7 puntos y el
    umbral queda a más de seis sigmas: lejos del ruido, pero sin fijar semilla,
    así que si el bot empeorara de verdad el test lo marca. Cuesta ~0,1s.
    """
    partidas = 300
    ganadas = 0

    for numero in range(partidas):
        # Se alterna el asiento para que no influya quién arranca de mano.
        bot_es = numero % 2
        estrategias = [bot.decidir, _al_azar] if bot_es == 0 else [_al_azar, bot.decidir]
        partida = _jugar_partida(estrategias, objetivo=15)
        ganadas += 1 if partida.ganador == bot_es else 0

    assert ganadas / partidas > 0.8
