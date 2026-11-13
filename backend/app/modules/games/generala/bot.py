"""El rival de la casa en la generala.

Dos decisiones por turno, y no pesan parecido:

1. **Qué dados guardar.** Acá está toda la habilidad del juego, y se resuelve
   calculando, no con reglas de dedo: para cada subconjunto que podría
   guardar, `calculo.py` enumera exactamente lo que rinde volver a tirar el
   resto, y se elige el mejor. Mirar una tirada adelante alcanza.

2. **Dónde anotar.** Se anota lo que más da, con dos correcciones: no quemar
   una fila cara por unos pocos puntos, y cuando no hay nada que anotar,
   tachar la que menos cuesta. Mueve mucho menos que la primera.

Por qué el bot calcula en vez de usar heurísticas, que es lo que hace el del
truco: porque acá se podía medir cuánto costaba no hacerlo. La primera versión
elegía los dados con reglas razonables (perseguir el grupo más grande, ir a la
escalera si falta uno) y perdía el 64,8% de las partidas contra un rival que
hacía esta cuenta, por 17 puntos de diferencia. Con el pago en 1,92 eso es la
casa perdiendo el 24% de cada apuesta: no era una cuestión de ajustar el
multiplicador, era el bot jugando mal.

A diferencia del truco, acá no hay información oculta ni bluff, así que el
techo de juego es alcanzable y conviene alcanzarlo.
"""

from collections import Counter

from app.modules.games.generala import calculo
from app.modules.games.generala.dados import (
    CATEGORIAS_NUMERICAS,
    DADOS,
    ESCALERAS,
    PUNTAJE_ARMADA,
)
from app.modules.games.shared import rng

__all__ = [
    "ORDEN_DE_SACRIFICIO",
    "PROBABILIDAD_DE_CALCULAR",
    "decidir",
    "elegir_categoria",
    "elegir_dados",
    "explicar_tirada",
]

# Qué se tacha primero cuando no queda nada que anotar. No es un detalle: el
# 30,8% de los turnos terminan en cero, así que esta lista se usa todo el
# tiempo.
#
# El orden salió de probar cinco candidatos cara a cara, 8000 partidas cada
# uno (`simular.py ordenes`). Este le gana a los otros cuatro por entre 1 y
# 2,3 puntos de porcentaje, y saca 122,9 puntos promedio contra 121,0 del peor.
#
# Lo que no funcionó, y es contraintuitivo: ordenar por valor esperado por
# turno. Medido suelto, el póker es la fila que más rinde (sale 20,8% de los
# turnos y paga 40, o sea 8,3 esperados) y la generala la que menos (3,6% por
# 50, o sea 1,8). Guardarse el póker para el final suena obvio y pierde: sale
# tan seguido que igual se llena, y reservarlo obliga a tachar filas mejores
# antes. La generala, al revés, conviene resignarla temprano: es la que más se
# termina tachando igual (6579 de 24500 ceros).
ORDEN_DE_SACRIFICIO = (
    "1",
    "generala",
    "2",
    "poker",
    "3",
    "escalera",
    "full",
    "4",
    "5",
    "6",
)

# Anotar una figura por debajo de esto, pudiendo esperarla, es malgastarla.
# Sólo frena cuando queda margen de turnos para volver a intentarla.
TURNOS_PARA_INSISTIR = 3


def decidir(partida, jugador: int) -> str:
    """La acción que juega el bot en el turno abierto."""
    turno = partida.turno
    if turno is None or turno.terminado:
        return None

    if turno.puede_tirar:
        indices = elegir_dados(turno)
        if indices:
            return "tirar:%s" % ",".join(str(indice) for indice in indices)

    return "anotar:%s" % elegir_categoria(turno, partida, jugador)


# Cuán seguido el bot hace la cuenta en vez de jugar por reglas de dedo. Es la
# perilla con la que se reparte la ventaja de la casa entre jugadores buenos y
# casuales, y no hay una respuesta que sirva para los dos (ver abajo).
PROBABILIDAD_DE_CALCULAR = 1.0


# ------------------------------ qué tirar ------------------------------

def elegir_dados(turno) -> list:
    """Los índices que conviene volver a tirar. Vacío si conviene quedarse."""
    if PROBABILIDAD_DE_CALCULAR < 1.0 and rng.uniform(0, 1) >= PROBABILIDAD_DE_CALCULAR:
        return _dados_por_heuristica(turno)

    indices, _, _ = calculo.mejor_jugada(
        turno.dados, turno.disponibles, turno.servida
    )
    return indices


def _dados_por_heuristica(turno) -> list:
    """Las reglas de dedo: perseguir el grupo más grande, o la escalera si
    falta un solo dado. Es como juega alguien en una mesa, sin calcular.
    """
    dados = turno.dados
    cuenta = Counter(dados)
    disponibles = set(turno.disponibles)

    if max(cuenta.values()) == DADOS:
        return []

    if "escalera" in disponibles and tuple(sorted(dados)) in ESCALERAS:
        return []

    if "full" in disponibles and sorted(cuenta.values()) == [2, 3]:
        if "poker" not in disponibles and "generala" not in disponibles:
            return []

    if "escalera" in disponibles and max(cuenta.values()) < 3:
        for escalera in ESCALERAS:
            if len(set(escalera) - set(dados)) != 1:
                continue

            vistos = set()
            sobrantes = []
            for indice, dado in enumerate(dados):
                if dado in escalera and dado not in vistos:
                    vistos.add(dado)
                else:
                    sobrantes.append(indice)

            if len(sobrantes) == 1:
                return sobrantes

    cara, _ = max(cuenta.items(), key=lambda par: (par[1], par[0]))
    return [indice for indice, dado in enumerate(dados) if dado != cara]


def explicar_tirada(turno) -> dict:
    """Lo que pesó la decisión. Para los tests y para poder discutirla."""
    indices, ahora, esperado = calculo.mejor_jugada(
        turno.dados, turno.disponibles, turno.servida
    )
    return {"tirar": indices, "anotando_ya": ahora, "esperado_si_tira": esperado}


# ------------------------------ dónde anotar ------------------------------

def elegir_categoria(turno, partida=None, jugador: int = 0) -> str:
    puntajes = turno.puntajes()
    con_puntos = {c: p for c, p in puntajes.items() if p > 0}

    if not con_puntos:
        return _sacrificar(turno.disponibles)

    categoria = max(con_puntos, key=lambda c: (con_puntos[c], _peso(c)))

    # No quemar una figura cara anotándola por poco: si es un número bajo y
    # queda partida por delante, conviene gastar otra cosa.
    if partida is not None and _es_desperdicio(categoria, con_puntos, partida, jugador):
        alternativa = _sacrificar(
            [c for c in turno.disponibles if c not in con_puntos]
        )
        if alternativa is not None:
            return alternativa

    return categoria


def _peso(categoria: str) -> int:
    """Desempate: a igual puntaje, gastar la categoría más barata."""
    return -ORDEN_DE_SACRIFICIO.index(categoria)


def _es_desperdicio(categoria, con_puntos, partida, jugador) -> bool:
    """Anotar 2 en la categoría del 6 es tirar a la basura la fila cara."""
    if categoria not in CATEGORIAS_NUMERICAS:
        return False

    cara = int(categoria)
    # Menos de dos dados de ese número es desaprovecharla.
    if con_puntos[categoria] >= cara * 2:
        return False

    quedan = len(partida.disponibles(jugador))
    return quedan > TURNOS_PARA_INSISTIR


def _sacrificar(disponibles) -> str:
    """Qué tachar con cero. El de menor valor esperado de los que quedan."""
    libres = set(disponibles)
    for categoria in ORDEN_DE_SACRIFICIO:
        if categoria in libres:
            return categoria

    return None


def valor_esperado_de_figura(categoria: str, probabilidad: float) -> float:
    """Lo que rinde dejar una figura abierta. Sirve para revisar el orden."""
    return PUNTAJE_ARMADA[categoria] * probabilidad
