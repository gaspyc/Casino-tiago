"""Las reglas de la generala: puntajes, turno, partida y dados verificables.

Esto no necesita base.
"""

from collections import Counter

import pytest

from app.modules.games.generala import bot, calculo
from app.modules.games.generala.dados import (
    CATEGORIAS,
    PUNTAJE_ARMADA,
    PUNTAJE_SERVIDA,
    es_generala,
    puntaje,
    puntajes_posibles,
)
from app.modules.games.generala.fairness import FlujoDeDados, tirar
from app.modules.games.generala.partida import Partida
from app.modules.games.generala.turno import TIRADAS_POR_TURNO, Turno, aplicar_accion


# ------------------------------ puntajes ------------------------------

def test_los_numeros_suman_los_dados_de_esa_cara():
    assert puntaje("4", [4, 4, 4, 1, 2]) == 12
    assert puntaje("6", [6, 6, 1, 1, 1]) == 12
    assert puntaje("1", [1, 1, 1, 1, 1]) == 5
    assert puntaje("3", [1, 2, 4, 5, 6]) == 0


def test_los_numeros_no_pagan_extra_por_servida():
    """Sumar cuatro cincos en la primera no es más difícil que en la tercera."""
    for servida in (True, False):
        assert puntaje("5", [5, 5, 5, 5, 1], servida=servida) == 20


def test_la_escalera_es_una_de_las_dos():
    assert puntaje("escalera", [1, 2, 3, 4, 5]) == 20
    assert puntaje("escalera", [5, 3, 2, 4, 6]) == 20
    assert puntaje("escalera", [1, 2, 3, 4, 5], servida=True) == 25
    # La del as arriba no vale acá.
    assert puntaje("escalera", [3, 4, 5, 6, 1]) == 0
    assert puntaje("escalera", [1, 1, 2, 3, 4]) == 0


def test_el_full_son_tres_y_dos_de_numeros_distintos():
    assert puntaje("full", [2, 2, 2, 5, 5]) == 30
    assert puntaje("full", [6, 6, 1, 1, 1], servida=True) == 35
    assert puntaje("full", [4, 4, 4, 4, 1]) == 0
    # Cinco iguales no es full.
    assert puntaje("full", [3, 3, 3, 3, 3]) == 0


def test_el_poker_son_cuatro_y_los_cinco_tambien():
    assert puntaje("poker", [5, 5, 5, 5, 2]) == 40
    assert puntaje("poker", [5, 5, 5, 5, 5]) == 40
    assert puntaje("poker", [5, 5, 5, 5, 2], servida=True) == 45
    assert puntaje("poker", [5, 5, 5, 2, 2]) == 0


def test_la_generala_son_los_cinco():
    assert puntaje("generala", [6, 6, 6, 6, 6]) == 50
    assert puntaje("generala", [6, 6, 6, 6, 6], servida=True) == 60
    assert puntaje("generala", [6, 6, 6, 6, 1]) == 0
    assert es_generala([2, 2, 2, 2, 2])
    assert not es_generala([2, 2, 2, 2, 3])


def test_la_servida_siempre_paga_mas():
    for categoria in PUNTAJE_ARMADA:
        assert PUNTAJE_SERVIDA[categoria] > PUNTAJE_ARMADA[categoria]


def test_no_existe_una_categoria_inventada():
    with pytest.raises(ValueError):
        puntaje("escalera_real", [1, 2, 3, 4, 5])


def test_siempre_son_cinco_dados():
    with pytest.raises(ValueError):
        puntaje("3", [3, 3, 3])


def test_los_puntajes_posibles_cubren_todas_las_categorias():
    posibles = puntajes_posibles([1, 2, 3, 4, 5])
    assert set(posibles) == set(CATEGORIAS)
    assert posibles["escalera"] == 20


# ------------------------------ dados verificables ------------------------------

def test_los_dados_salen_del_seed_y_se_rehacen():
    primera = tirar("seed", "cliente", 1, [5, 3, 2])

    assert tirar("seed", "cliente", 1, [5, 3, 2]) == primera
    assert tirar("seed", "cliente", 2, [5, 3, 2]) != primera
    assert tirar("otro", "cliente", 1, [5, 3, 2]) != primera


def test_el_flujo_no_repite_dados_entre_tiradas():
    """Cada tirada consume bytes nuevos: si no, el turno saldría clonado."""
    flujo = FlujoDeDados("seed", "cliente", 1)
    primera = flujo.tirar(5)
    segunda = flujo.tirar(5)

    assert flujo.tirados == 10
    assert primera != segunda


def test_los_dados_caen_parejo():
    """256 no es múltiplo de 6: sin muestreo con rechazo el 5 y el 6 saldrían menos."""
    flujo = FlujoDeDados("seed", "cliente", 1)
    salidas = Counter(flujo.tirar(300_000))

    assert set(salidas) == {1, 2, 3, 4, 5, 6}

    esperado = 300_000 / 6
    peor = max(abs(cuenta - esperado) / esperado for cuenta in salidas.values())
    assert peor < 0.02, "desvio del %.2f por ciento" % (peor * 100)


# ------------------------------ el turno ------------------------------

def _turno(nonce=1, disponibles=CATEGORIAS):
    return Turno(FlujoDeDados("seed", "cliente", nonce), disponibles)


def test_el_turno_arranca_servido_y_deja_de_estarlo_al_tirar():
    turno = _turno()

    assert turno.servida
    assert turno.tirada == 1
    assert len(turno.dados) == 5

    turno.tirar([0])
    assert not turno.servida
    assert turno.tirada == 2


def test_solo_se_tira_tres_veces():
    turno = _turno()
    turno.tirar([0])
    turno.tirar([0])

    assert turno.tirada == TIRADAS_POR_TURNO
    assert not turno.puede_tirar

    with pytest.raises(ValueError):
        turno.tirar([0])


def test_tirar_cambia_solo_los_dados_elegidos():
    turno = _turno()
    antes = list(turno.dados)

    turno.tirar([1, 3])

    assert turno.dados[0] == antes[0]
    assert turno.dados[2] == antes[2]
    assert turno.dados[4] == antes[4]


def test_no_se_tiran_dados_que_no_existen():
    turno = _turno()

    with pytest.raises(ValueError):
        turno.tirar([5])

    with pytest.raises(ValueError):
        turno.tirar([])


def test_anotar_cierra_el_turno_y_no_se_puede_dos_veces():
    turno = _turno()
    turno.anotar("1")

    assert turno.terminado
    assert turno.categoria == "1"
    assert turno.acciones() == []

    with pytest.raises(ValueError):
        turno.anotar("2")


def test_no_se_anota_en_una_categoria_usada():
    turno = _turno(disponibles=["3", "full"])

    with pytest.raises(ValueError):
        turno.anotar("escalera")


def test_se_puede_tachar_con_cero():
    """Anotar es obligatorio: si nada sirve, se sacrifica una categoría."""
    turno = _turno(disponibles=["generala"])
    puntos = turno.anotar("generala")

    assert puntos == 0
    assert turno.terminado


def test_las_acciones_del_registro_se_vuelven_a_aplicar():
    turno = _turno()
    aplicar_accion(turno, "tirar:0,2")
    aplicar_accion(turno, "anotar:4")

    assert turno.terminado
    assert turno.categoria == "4"

    with pytest.raises(ValueError):
        aplicar_accion(turno, "bailar:1")


# ------------------------------ la partida ------------------------------

def _jugar_entera(nonce, empieza=0):
    partida = Partida("seed", "cliente", nonce, empieza=empieza)
    while not partida.terminada:
        accion = bot.decidir(partida, partida.en_turno)
        if accion is None:
            break

        aplicar_accion(partida.turno, accion)
        if partida.turno.terminado:
            partida.cerrar_turno()

    return partida


def test_una_partida_llena_las_dos_planillas():
    partida = _jugar_entera(3)

    assert partida.terminada
    if partida.generala_servida_de is None:
        assert partida.turnos_jugados == len(CATEGORIAS) * 2
        for jugador in (0, 1):
            assert all(
                puntos is not None for puntos in partida.planillas[jugador].values()
            )


def test_gana_el_que_mas_suma():
    partida = _jugar_entera(5)

    if partida.generala_servida_de is not None:
        pytest.skip("Cortó por generala servida")

    uno, otro = partida.total(0), partida.total(1)
    if uno == otro:
        assert partida.ganador is None
    else:
        assert partida.ganador == (0 if uno > otro else 1)


def test_el_turno_se_alterna():
    partida = Partida("seed", "cliente", 7, empieza=1)
    assert partida.en_turno == 1

    aplicar_accion(partida.turno, "anotar:%s" % partida.turno.disponibles[0])
    partida.cerrar_turno()

    if not partida.terminada:
        assert partida.en_turno == 0


def test_la_partida_se_rehace_igual_desde_las_acciones():
    """Es lo que permite guardar sólo el registro y no el estado."""
    original = Partida("seed", "cliente", 11)
    acciones = []

    while not original.terminada:
        accion = bot.decidir(original, original.en_turno)
        if accion is None:
            break

        acciones.append(accion)
        aplicar_accion(original.turno, accion)
        if original.turno.terminado:
            original.cerrar_turno()

    copia = Partida("seed", "cliente", 11)
    for accion in acciones:
        if copia.terminada:
            break

        aplicar_accion(copia.turno, accion)
        if copia.turno.terminado:
            copia.cerrar_turno()

    assert copia.planillas == original.planillas
    assert copia.ganador == original.ganador
    assert [copia.total(0), copia.total(1)] == [
        original.total(0),
        original.total(1),
    ]


def test_la_generala_servida_corta_la_partida():
    partida = Partida("seed", "cliente", 1)
    partida.turno.dados = [4, 4, 4, 4, 4]
    partida._resolver_generala_servida()

    assert partida.terminada
    assert partida.ganador == partida.generala_servida_de
    assert partida.planillas[partida.generala_servida_de]["generala"] == 60


def test_con_la_generala_tachada_la_servida_no_da_nada():
    """El caso que rompía el motor: no se puede anotar en una fila usada."""
    partida = Partida("seed", "cliente", 1)
    jugador = partida.en_turno
    partida.planillas[jugador]["generala"] = 0

    partida.turno.dados = [4, 4, 4, 4, 4]
    partida._resolver_generala_servida()

    assert not partida.terminada
    assert partida.ganador is None
    assert partida.planillas[jugador]["generala"] == 0


def test_la_doble_generala_tambien_gana():
    partida = Partida("seed", "cliente", 1)
    jugador = partida.en_turno
    partida.planillas[jugador]["generala"] = 50

    partida.turno.dados = [2, 2, 2, 2, 2]
    partida._resolver_generala_servida()

    assert partida.terminada
    assert partida.ganador == jugador
    # No se pisa lo que ya estaba anotado.
    assert partida.planillas[jugador]["generala"] == 50


# ------------------------------ el bot ------------------------------

def test_el_bot_se_queda_con_la_generala_hecha():
    turno = _turno()
    turno.dados = [6, 6, 6, 6, 6]

    assert bot.elegir_dados(turno) == []


def test_el_bot_no_rompe_la_escalera_hecha():
    turno = _turno(disponibles=["escalera", "1", "2"])
    turno.dados = [1, 2, 3, 4, 5]

    assert bot.elegir_dados(turno) == []


def test_el_bot_tira_lo_que_no_sirve():
    turno = _turno(disponibles=list(CATEGORIAS))
    turno.dados = [6, 6, 6, 1, 2]

    # Guarda los seises y cambia los otros dos.
    assert bot.elegir_dados(turno) == [3, 4]


def test_el_bot_tacha_lo_que_menos_cuesta():
    turno = _turno(disponibles=["generala", "6", "escalera"])
    turno.dados = [1, 1, 2, 2, 3]  # no da puntos en ninguna

    assert bot.elegir_categoria(turno) == "generala"


def test_el_bot_anota_lo_que_mas_da():
    turno = _turno(disponibles=["full", "2", "5"])
    turno.dados = [2, 2, 2, 5, 5]

    assert bot.elegir_categoria(turno) == "full"


def test_el_bot_siempre_devuelve_una_accion_jugable():
    """Si devolviera algo inválido, la partida contra la casa se trabaría."""
    for nonce in range(60):
        partida = Partida("seed", "cliente", nonce)

        while not partida.terminada:
            accion = bot.decidir(partida, partida.en_turno)
            assert accion is not None
            aplicar_accion(partida.turno, accion)
            if partida.turno.terminado:
                partida.cerrar_turno()


# ------------------------------ la cuenta del bot ------------------------------

def test_la_esperanza_se_calcula_enumerando_y_da_exacto():
    """Cuatro seises guardados, uno al aire, y sólo la fila del 6 disponible.

    Son 24 seguros más 6 por la chance de 1/6 de que el quinto salga seis: 25
    justos. Se puede verificar a mano, que es la gracia de enumerar.
    """
    esperado = calculo.esperado_guardando((6, 6, 6, 6), 1, ("6",))
    assert abs(esperado - 25.0) < 1e-9


def test_la_esperanza_exige_cinco_dados_en_total():
    with pytest.raises(ValueError):
        calculo.esperado_guardando((), 1, ("6",))


def test_guardar_todo_no_puede_valer_menos_que_lo_que_ya_hay():
    for nonce in range(30):
        turno = _turno(nonce)
        indices, ahora, esperado = calculo.mejor_jugada(
            turno.dados, turno.disponibles, turno.servida
        )
        assert esperado >= ahora
        # Si no conviene tirar, no tira.
        assert indices or esperado == ahora


def test_la_cuenta_prefiere_tirar_cuando_la_mano_es_mala():
    turno = _turno(disponibles=list(CATEGORIAS))
    turno.dados = [1, 2, 2, 3, 6]

    indices, _, _ = calculo.mejor_jugada(turno.dados, turno.disponibles, True)
    assert indices
