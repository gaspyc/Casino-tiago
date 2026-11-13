"""El solver exacto de la generala.

Este número fija la tabla de pagos, así que no alcanza con que corra: tiene
que estar cruzado contra algo que no sea él mismo. Acá hay tres cruces:

- las estructuras (252 tiradas, 462 guardables, las filas de la transición
  suman 1),
- el valor de los finales de partida contra una enumeración recursiva escrita
  aparte, que no comparte código con el solver,
- y que ninguna política medible lo supere, porque es una cota superior.
"""

from functools import lru_cache
from itertools import combinations_with_replacement

import pytest

try:
    from app.modules.games.generala.dados import CATEGORIAS, DADOS, puntaje
    from app.modules.games.generala.optimo import (
        DADOS_POSIBLES,
        GUARDABLES,
        _transicion,
        distribucion_de_la_primera,
        jugada_optima,
        resolver,
        techo_del_pago,
        valor_de_la_partida,
    )
except Exception as exc:  # pragma: no cover - entorno sin dependencias
    pytest.skip("No se pudo importar el solver (%s)" % exc, allow_module_level=True)

CARAS = tuple(range(1, 7))


# ------------------------------ las estructuras ------------------------------

def test_las_tiradas_posibles_son_252():
    assert len(DADOS_POSIBLES) == 252
    assert len(set(DADOS_POSIBLES)) == 252
    assert all(list(d) == sorted(d) for d in DADOS_POSIBLES)


def test_los_guardables_son_462():
    """De 0 a 5 dados: 1 + 6 + 21 + 56 + 126 + 252."""
    assert len(GUARDABLES) == 462
    assert len(set(GUARDABLES)) == 462


def test_la_primera_tirada_es_una_distribucion():
    probabilidades = distribucion_de_la_primera()
    assert len(probabilidades) == 252
    assert abs(sum(probabilidades) - 1) < 1e-12
    assert all(p > 0 for p in probabilidades)


def test_cada_fila_de_la_transicion_suma_uno():
    for guardado, destinos in zip(GUARDABLES, _transicion()):
        total = sum(probabilidad for _, probabilidad in destinos)
        assert abs(total - 1) < 1e-12, guardado


def test_guardar_los_cinco_dados_no_cambia_nada():
    """Plantarse tiene que ser quedarse donde estás, o el solver se miente."""
    transicion = _transicion()

    for indice, guardado in enumerate(GUARDABLES):
        if len(guardado) != DADOS:
            continue

        destinos = transicion[indice]
        assert len(destinos) == 1
        assert abs(destinos[0][1] - 1) < 1e-12
        assert DADOS_POSIBLES[destinos[0][0]] == guardado


def test_la_transicion_es_rala():
    """Es la razón por la que esto corre en Python puro."""
    nulos = sum(len(destinos) for destinos in _transicion())
    assert nulos == 4368
    assert nulos < len(GUARDABLES) * len(DADOS_POSIBLES) / 20


# --------------------- cruce contra una enumeración aparte ---------------------
# Esta parte no usa nada del solver: resuelve el turno por recursión directa
# sobre las tiradas. Si los dos coinciden, el error tendría que estar en los
# dos a la vez y de la misma forma.

@lru_cache(maxsize=None)
def _mejor_turno(dados, tiradas_restantes, categoria, servida):
    """E[puntaje] de este turno jugando perfecto, con una sola categoría."""
    anotar = puntaje(categoria, list(dados), servida=servida)

    if tiradas_restantes == 0:
        return float(anotar)

    mejor = float(anotar)

    for cantidad in range(DADOS + 1):
        for guardado in set(combinations_with_replacement(dados, cantidad)):
            if not _se_puede_guardar(guardado, dados):
                continue
            if len(guardado) == DADOS:
                continue

            faltan = DADOS - len(guardado)
            total = 0.0

            for tirada in _todas_las_tiradas(faltan):
                final = tuple(sorted(guardado + tirada))
                total += _mejor_turno(final, tiradas_restantes - 1, categoria, False)

            esperado = total / 6 ** faltan
            mejor = max(mejor, esperado)

    return mejor


@lru_cache(maxsize=None)
def _todas_las_tiradas(cantidad):
    """Todas las tiradas ORDENADAS, sin reducir a multiconjunto: 6^k."""
    if cantidad == 0:
        return ((),)

    return tuple(
        resto + (cara,)
        for resto in _todas_las_tiradas(cantidad - 1)
        for cara in CARAS
    )


def _se_puede_guardar(guardado, dados):
    quedan = list(dados)
    for dado in guardado:
        if dado not in quedan:
            return False
        quedan.remove(dado)
    return True


@pytest.mark.parametrize("categoria", ["6", "poker", "escalera"])
def test_el_final_de_partida_coincide_con_la_enumeracion(categoria):
    """Con una sola fila libre, el solver y la enumeración tienen que dar igual."""
    indice = CATEGORIAS.index(categoria)
    mascara = ((1 << len(CATEGORIAS)) - 1) & ~(1 << indice)

    del_solver = resolver()[mascara]

    primera = distribucion_de_la_primera()
    enumerado = sum(
        probabilidad * _mejor_turno(DADOS_POSIBLES[d], 2, categoria, True)
        for d, probabilidad in enumerate(primera)
    )

    assert abs(del_solver - enumerado) < 1e-9


# ------------------------------ el valor ------------------------------

def test_la_planilla_llena_no_vale_nada():
    llena = (1 << len(CATEGORIAS)) - 1
    assert resolver()[llena] == 0.0


def test_mas_filas_libres_nunca_vale_menos():
    """Sacar una categoría de la planilla no puede mejorarte."""
    valor = resolver()

    for mascara in range(0, 1 << len(CATEGORIAS), 7):
        for bit in range(len(CATEGORIAS)):
            if mascara & (1 << bit):
                continue
            # mascara tiene esa fila libre, mascara|bit no.
            assert valor[mascara] >= valor[mascara | (1 << bit)] - 1e-9


def test_el_optimo_le_gana_a_todo_lo_medido():
    """Es una cota superior: ninguna política puede sacarle más puntos."""
    optimo = valor_de_la_partida()

    # Medidos con 400k planillas cada uno (ver simular.py pagos).
    assert optimo > 140.8, optimo   # el bot de la casa
    assert optimo > 139.5, optimo   # la calculadora de 1 tirada
    assert optimo > 124.0, optimo   # la heuristica casual
    assert optimo < 200, optimo     # cota de cordura


def test_el_valor_es_estable():
    assert valor_de_la_partida() == valor_de_la_partida()
    assert abs(valor_de_la_partida() - 149.17) < 0.01


# ------------------------------ el premio por servida ------------------------------

def test_el_premio_por_servida_sube_el_techo():
    """Con premio, el juego perfecto cuida la generala y saca más.

    Es justamente por esto que el parámetro existe: calcular el techo sin él
    daría un número bajo y la casa quedaría corta de ventaja.
    """
    sin_premio = valor_de_la_partida(0.0)
    con_premio = valor_de_la_partida(500.0)

    assert con_premio > sin_premio
    # Y no por el premio solo: el valor sube más que 500 veces la chance de
    # servida jugando sin cuidarla, porque la política cambia.
    assert con_premio - sin_premio > 2.0


def test_el_premio_por_servida_es_monotono():
    valores = [valor_de_la_partida(bonus) for bonus in (0.0, 100.0, 400.0, 1000.0)]
    assert valores == sorted(valores)


def test_el_techo_del_pago_es_el_valor_por_la_pendiente():
    umbral, por_punto, premio = 70.0, 0.006, 3.0
    bonus = premio / por_punto

    esperado = por_punto * (valor_de_la_partida(bonus) - umbral)
    assert abs(techo_del_pago(umbral, por_punto, premio) - esperado) < 1e-12


# ------------------------------ la política ------------------------------

def test_la_jugada_optima_es_legal():
    libres = list(CATEGORIAS)
    dados = [1, 2, 3, 4, 5]

    que, cual = jugada_optima(dados, libres, 1)

    assert que in ("anotar", "tirar")
    if que == "anotar":
        assert cual in libres
    else:
        assert all(0 <= indice < DADOS for indice in cual)
        assert len(set(cual)) == len(cual)


def test_con_la_ultima_tirada_siempre_anota():
    que, cual = jugada_optima([2, 3, 4, 6, 6], list(CATEGORIAS), 3)
    assert que == "anotar"
    assert cual in CATEGORIAS


def test_la_generala_servida_se_anota_y_no_se_tira():
    """Cinco iguales en la primera son 60 puntos: tirar sería tirarlos."""
    que, cual = jugada_optima([4, 4, 4, 4, 4], list(CATEGORIAS), 1)
    assert (que, cual) == ("anotar", "generala")


def test_con_una_escalera_servida_no_vuelve_a_tirar():
    que, cual = jugada_optima([1, 2, 3, 4, 5], ["escalera"], 1)
    assert (que, cual) == ("anotar", "escalera")


def test_persigue_el_grupo_grande_cuando_le_queda_el_poker():
    """Con tres seises y dos sueltos, lo que se tira son los dos sueltos."""
    que, indices = jugada_optima([6, 6, 6, 2, 3], ["poker", "generala"], 1)
    assert que == "tirar"
    assert sorted(indices) == [3, 4]


def test_la_politica_optima_juega_una_partida_entera():
    """Cruce contra el motor de producción: 10 turnos, planilla llena."""
    from app.modules.games.generala.partida import Partida

    partida = Partida("semilla-de-prueba", "cliente", 0, empieza=0, corta_servida_de=())

    while not partida.terminada:
        turno = partida.turno
        que, cual = jugada_optima(turno.dados, turno.disponibles, turno.tirada)

        if que == "anotar":
            turno.anotar(cual)
        else:
            turno.tirar(cual)

        if turno.terminado:
            partida.cerrar_turno()

    assert partida.turnos_jugados == 2 * len(CATEGORIAS)
    assert all(puntos is not None for puntos in partida.planillas[0].values())
    assert partida.total(0) > 0
