"""El techo exacto de la generala: cuánto saca el que juega perfecto.

Por qué hace falta
------------------
La tabla de pagos por puntaje se diseña contra el mejor jugador posible, no
contra el mejor que yo pueda programar a ojo. El bot y la "calculadora" de
`simular.py` miran una sola tirada adelante, así que **subestiman** el techo:
fijar el pago con ese número deja a la casa expuesta a cualquiera que juegue
mejor, y con provably fair y una API pública alguien va a escribir ese bot.

Esto resuelve la partida entera, sin heurística y sin simular. Es la misma
estructura con la que se resuelve el Yahtzee.

Cómo
----
El estado es qué categorías quedan libres: 2^10 = 1024 subconjuntos. Se
recorren de la planilla llena hacia la vacía, y para cada uno se resuelve el
turno completo —tres tiradas, con la decisión de qué dados guardar en cada
una— por valor esperado exacto.

El turno se resuelve hacia atrás:

    final[d]   = mejor puntaje anotable con los dados d, más el valor del
                 estado que queda después de anotar
    segunda[d] = max sobre los subconjuntos k de d de E[final | guardo k]
    primera[d] = lo mismo una tirada antes, contra la opción de anotar servida

Guardar los cinco dados es un subconjunto válido, así que "plantarse y anotar"
sale solo, sin ser un caso aparte.

Por qué es barato
-----------------
La matriz de transición —la chance de terminar en los dados d' habiendo
guardado k— no depende de qué categorías queden libres, así que se calcula una
sola vez. Y es rala: guardar cuatro dados deja seis finales posibles, no 252.
En total tiene 4368 entradas no nulas sobre 116 mil, que es la razón por la
que esto corre en Python puro sin necesidad de numpy.

Lo que NO cubre
---------------
Maximiza el PUNTAJE esperado, no el pago esperado. Son lo mismo mientras la
tabla de pagos sea afín en el puntaje; cuando deja de serlo —un umbral abajo,
un escalón grande arriba— el jugador óptimo empieza a arriesgar distinto y
este número se queda corto. Es la razón por la que la tabla se diseña casi
afín: para que este techo siga siendo el techo.

    python -m app.modules.games.generala.optimo
"""

from collections import Counter
from functools import lru_cache
from itertools import combinations_with_replacement
from math import factorial

from app.modules.games.generala.dados import CATEGORIAS, DADOS, puntaje

__all__ = [
    "DADOS_POSIBLES",
    "GUARDABLES",
    "distribucion_de_la_primera",
    "jugada_optima",
    "resolver",
    "valor_de_la_partida",
]

CARAS = tuple(range(1, 7))
LLENA = (1 << len(CATEGORIAS)) - 1

# Los 252 resultados posibles de cinco dados, como multiconjuntos ordenados.
DADOS_POSIBLES = tuple(combinations_with_replacement(CARAS, DADOS))
INDICE_DADOS = {dados: i for i, dados in enumerate(DADOS_POSIBLES)}

# Todo lo que se puede guardar: multiconjuntos de 0 a 5 dados. Son 462.
GUARDABLES = tuple(
    guardado
    for cantidad in range(DADOS + 1)
    for guardado in combinations_with_replacement(CARAS, cantidad)
)
INDICE_GUARDABLES = {guardado: i for i, guardado in enumerate(GUARDABLES)}


def _peso(multiconjunto) -> int:
    """Cuántos resultados ordenados dan este multiconjunto."""
    peso = factorial(len(multiconjunto))
    for veces in Counter(multiconjunto).values():
        peso //= factorial(veces)
    return peso


@lru_cache(maxsize=1)
def _transicion():
    """Para cada k, la lista [(indice de d', probabilidad)] al tirar el resto.

    Rala a propósito: guardar cuatro dados deja seis finales posibles.
    """
    salida = []

    for guardado in GUARDABLES:
        faltan = DADOS - len(guardado)
        total = 6 ** faltan
        destinos = {}

        for tirada in combinations_with_replacement(CARAS, faltan):
            final = tuple(sorted(guardado + tirada))
            indice = INDICE_DADOS[final]
            destinos[indice] = destinos.get(indice, 0.0) + _peso(tirada) / total

        salida.append(tuple(destinos.items()))

    return tuple(salida)


@lru_cache(maxsize=1)
def _guardables_de():
    """Para cada tirada d, los índices de los k que se pueden guardar de d."""
    salida = []

    for dados in DADOS_POSIBLES:
        indices = set()
        for cantidad in range(DADOS + 1):
            for guardado in combinations_with_replacement(sorted(set(dados)), cantidad):
                if _cabe(guardado, dados):
                    indices.add(INDICE_GUARDABLES[tuple(sorted(guardado))])
        salida.append(tuple(sorted(indices)))

    return tuple(salida)


def _cabe(guardado, dados) -> bool:
    """¿Se puede formar `guardado` sacando dados de `dados`?"""
    disponibles = Counter(dados)
    for cara, veces in Counter(guardado).items():
        if disponibles[cara] < veces:
            return False
    return True


@lru_cache(maxsize=1)
def _puntajes():
    """puntos[servida][indice de categoria][indice de dados], de la producción."""
    return {
        servida: tuple(
            tuple(puntaje(categoria, dados, servida=servida) for dados in DADOS_POSIBLES)
            for categoria in CATEGORIAS
        )
        for servida in (False, True)
    }


@lru_cache(maxsize=1)
def distribucion_de_la_primera():
    """La distribución de una tirada de cinco dados, sobre DADOS_POSIBLES."""
    return tuple(_peso(dados) / 6 ** DADOS for dados in DADOS_POSIBLES)


@lru_cache(maxsize=8)
def resolver(bonus_servida: float = 0.0):
    """Resuelve la partida. Devuelve la lista valor[mascara].

    La máscara tiene un bit por categoría en el orden de CATEGORIAS, prendido
    cuando la categoría ya está usada. valor[0] es la planilla vacía, o sea
    los puntos esperados de una partida entera jugada perfecto.

    `bonus_servida` son puntos extra por anotar la generala servida, y es cómo
    se modela un premio aparte por la servida sin perder la exactitud. Si el
    pago es afín —multiplicador = a·(puntaje − umbral)— entonces un premio de
    J por la servida equivale a J/a puntos, porque

        a·(S − U) + J·[servida] = a·(S + (J/a)·[servida] − U)

    y el corchete entra adentro de la esperanza como un punto más. Importa
    porque con premio el jugador perfecto deja de jugar igual: le conviene
    cuidar la fila de la generala para conservar la chance. Sin este
    parámetro, el techo que calcula esto se quedaría corto justo en la tabla
    que lo tiene.
    """
    transicion = _transicion()
    guardables = _guardables_de()
    puntos = _puntajes()
    primera_tirada = distribucion_de_la_primera()
    cantidad_dados = len(DADOS_POSIBLES)

    valor = [0.0] * (1 << len(CATEGORIAS))

    # De la planilla más llena a la más vacía, así los estados que hacen falta
    # ya están resueltos.
    for mascara in sorted(range(1 << len(CATEGORIAS)), key=lambda m: -bin(m).count("1")):
        if mascara == LLENA:
            continue

        libres = [i for i in range(len(CATEGORIAS)) if not mascara & (1 << i)]
        despues = [valor[mascara | (1 << i)] for i in libres]

        # Anotar con la última tirada, sin bonus de servida.
        armada = puntos[False]
        final = [
            max(armada[c][d] + despues[j] for j, c in enumerate(libres))
            for d in range(cantidad_dados)
        ]

        # Una tirada antes: se elige el mejor subconjunto a guardar.
        segunda = _mejor_guardando(final, transicion, guardables)

        # La primera: acá existe el bonus de servida, y hay que compararlo
        # contra volver a tirar, porque tirar lo pierde.
        servido = puntos[True]
        anotar_servida = [
            max(
                servido[c][d]
                + despues[j]
                + (bonus_servida if _es_generala_servida(c, d) else 0.0)
                for j, c in enumerate(libres)
            )
            for d in range(cantidad_dados)
        ]
        volver_a_tirar = _mejor_guardando(segunda, transicion, guardables)

        valor[mascara] = sum(
            probabilidad * max(anotar_servida[d], volver_a_tirar[d])
            for d, probabilidad in enumerate(primera_tirada)
        )

    return valor


@lru_cache(maxsize=1)
def _indice_generala():
    return CATEGORIAS.index("generala")


def _es_generala_servida(categoria_indice: int, dados_indice: int) -> bool:
    """¿Anotar esta categoría con estos dados es una generala servida?"""
    return (
        categoria_indice == _indice_generala()
        and len(set(DADOS_POSIBLES[dados_indice])) == 1
    )


def _mejor_guardando(siguiente, transicion, guardables):
    """Para cada tirada, el valor del mejor subconjunto que puede guardar."""
    por_guardado = [
        sum(probabilidad * siguiente[destino] for destino, probabilidad in destinos)
        for destinos in transicion
    ]

    return [
        max(por_guardado[k] for k in indices)
        for indices in guardables
    ]


def valor_de_la_partida(bonus_servida: float = 0.0) -> float:
    """Los puntos esperados de una planilla jugada perfecto."""
    return resolver(bonus_servida)[0]


def techo_del_pago(umbral: float, por_punto: float, premio_servida: float = 0.0) -> float:
    """El RTP del que juega perfecto bajo un pago afín. El techo de la casa.

    Vale exacto mientras el umbral casi nunca muerda: abajo del umbral el pago
    se aplana en cero y deja de ser afín, y ahí el óptimo de puntaje deja de
    ser el óptimo de pago. Con el umbral puesto donde el óptimo casi nunca
    llega, la diferencia es despreciable; la verificación está en los tests.
    """
    bonus = premio_servida / por_punto if por_punto else 0.0
    return por_punto * (valor_de_la_partida(bonus) - umbral)


@lru_cache(maxsize=2048)
def _tablero(mascara: int, bonus_servida: float = 0.0):
    """Todo lo que depende sólo de qué categorías quedan libres.

    Se cachea porque `jugada_optima` se llama hasta tres veces por turno y lo
    caro —recorrer los 462 subconjuntos guardables— no cambia dentro del
    turno. Sin esto, resolver una partida cuesta treinta veces más.
    """
    valor = resolver(bonus_servida)
    transicion = _transicion()
    guardables = _guardables_de()
    puntos = _puntajes()
    cantidad = len(DADOS_POSIBLES)

    libres = [i for i in range(len(CATEGORIAS)) if not mascara & (1 << i)]
    despues = [valor[mascara | (1 << i)] for i in libres]

    armada = puntos[False]
    final = [
        max(armada[i][d] + despues[j] for j, i in enumerate(libres))
        for d in range(cantidad)
    ]
    segunda = _mejor_guardando(final, transicion, guardables)

    # Lo que vale cada subconjunto guardable, según cuántas tiradas quedan.
    por_guardado = {
        2: [
            sum(probabilidad * final[destino] for destino, probabilidad in destinos)
            for destinos in transicion
        ],
        1: [
            sum(probabilidad * segunda[destino] for destino, probabilidad in destinos)
            for destinos in transicion
        ],
    }

    return libres, despues, por_guardado


def jugada_optima(dados, libres, tirada: int, bonus_servida: float = 0.0):
    """Qué conviene hacer con estos dados, jugando perfecto.

    `libres` son los nombres de las categorías sin usar y `tirada` va de 1 a 3.
    `bonus_servida` es el premio por la servida, en puntos (ver `resolver`):
    con premio, el juego perfecto cuida la fila de la generala.

    Devuelve ("anotar", categoria) o ("tirar", indices).
    """
    sin_usar = set(libres)
    mascara = 0
    for i, categoria in enumerate(CATEGORIAS):
        if categoria not in sin_usar:
            mascara |= 1 << i

    indices_libres, despues, por_guardado = _tablero(mascara, bonus_servida)

    ordenados = tuple(sorted(dados))
    indice = INDICE_DADOS[ordenados]
    servida = tirada == 1
    puntos = _puntajes()[servida]

    mejor_categoria, mejor_anotar = None, None
    for j, i in enumerate(indices_libres):
        total = puntos[i][indice] + despues[j]
        if servida and _es_generala_servida(i, indice):
            total += bonus_servida
        if mejor_anotar is None or total > mejor_anotar:
            mejor_anotar, mejor_categoria = total, CATEGORIAS[i]

    if tirada >= 3:
        return ("anotar", mejor_categoria)

    valores = por_guardado[tirada]
    mejor_guardado, mejor_tirar = None, None
    for k in _guardables_de()[indice]:
        if mejor_tirar is None or valores[k] > mejor_tirar:
            mejor_tirar, mejor_guardado = valores[k], GUARDABLES[k]

    if mejor_anotar >= mejor_tirar:
        return ("anotar", mejor_categoria)

    # Los índices a volver a tirar son los que sobran después de apartar el
    # multiconjunto que conviene guardar.
    quedan = Counter(mejor_guardado)
    indices = []
    for posicion, dado in enumerate(dados):
        if quedan[dado]:
            quedan[dado] -= 1
        else:
            indices.append(posicion)

    return ("tirar", indices)


if __name__ == "__main__":
    import time

    arranque = time.time()
    esperado = valor_de_la_partida()
    print("resuelto en %.1f s" % (time.time() - arranque))
    print()
    print("puntaje esperado jugando perfecto: %.2f" % esperado)
    print()
    print("medido por simulacion, para comparar:")
    for nombre, puntos in (
        ("bot de la casa", 140.6),
        ("calculadora (1 tirada vista)", 139.4),
        ("heuristica (casual)", 122.7),
    ):
        print("  %-30s %6.1f   (%+.1f%% vs el optimo)"
              % (nombre, puntos, 100 * (puntos / esperado - 1)))
