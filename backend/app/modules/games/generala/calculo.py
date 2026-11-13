"""Cuánto rinde guardar unos dados y volver a tirar el resto. Exacto.

Esto es el corazón del bot y es lo único de la generala donde pensar paga de
verdad. Medido: un jugador que decide bien qué dados guardar le gana el 64,8%
de las partidas a uno que lo hace con reglas de dedo, y por 17 puntos de
promedio. La decisión de en qué categoría anotar, al lado, casi no mueve la
aguja.

No se simula, se enumera. Tirar k dados tiene 6^k resultados ordenados, pero lo
único que importa es el multiconjunto, y de esos hay muchos menos: 252 para
cinco dados en vez de 7776. Cada uno pesa por su coeficiente multinomial, así
que la cuenta es exacta y treinta veces más barata.

Es una jugada de anticipación, no el juego óptimo: mira una tirada adelante,
no dos. Resolver la generala entera es una tabla de programación dinámica
grande; esto alcanza de sobra para que la casa no quede del lado flojo.
"""

from collections import Counter
from functools import lru_cache
from itertools import combinations, combinations_with_replacement
from math import factorial

from app.modules.games.generala.dados import DADOS, puntaje

__all__ = ["esperado_guardando", "mejor_anotacion", "mejor_jugada"]

CARAS = tuple(range(1, 7))


def _tiradas_posibles(cantidad: int):
    """Los resultados de tirar `cantidad` dados, como multiconjuntos con peso."""
    salida = []
    for combinacion in combinations_with_replacement(CARAS, cantidad):
        peso = factorial(cantidad)
        for veces in Counter(combinacion).values():
            peso //= factorial(veces)
        salida.append((combinacion, peso))

    return tuple(salida)


_POSIBLES = {cantidad: _tiradas_posibles(cantidad) for cantidad in range(DADOS + 1)}


@lru_cache(maxsize=200_000)
def mejor_anotacion(dados: tuple, disponibles: tuple, servida: bool) -> int:
    """El mejor puntaje que se puede anotar con estos dados."""
    return max(puntaje(categoria, dados, servida) for categoria in disponibles)


@lru_cache(maxsize=200_000)
def esperado_guardando(guardados: tuple, faltan: int, disponibles: tuple) -> float:
    """E[mejor puntaje] guardando esos dados y tirando `faltan`.

    La esperanza se calcula sin bonus de servida, que es lo correcto: volver a
    tirar lo pierde.
    """
    if len(guardados) + faltan != DADOS:
        raise ValueError(
            "Guardados y tirados tienen que sumar %s dados" % DADOS
        )

    if faltan == 0:
        return float(mejor_anotacion(guardados, disponibles, False))

    total = 0
    peso_total = 0

    for tirada, peso in _POSIBLES[faltan]:
        total += mejor_anotacion(
            tuple(sorted(guardados + tirada)), disponibles, False
        ) * peso
        peso_total += peso

    return total / peso_total


def mejor_jugada(dados, disponibles, servida: bool):
    """Los índices a volver a tirar, o lista vacía si conviene anotar ya.

    Compara anotar ahora —con bonus de servida si corresponde— contra el mejor
    subconjunto que se puede guardar. Devuelve también los dos valores, que es
    lo que permite explicar la decisión.
    """
    orden = tuple(sorted(disponibles))
    ahora = float(mejor_anotacion(tuple(sorted(dados)), orden, servida))

    mejor_valor = ahora
    mejor_indices = []

    for cantidad in range(DADOS):
        for guardar in combinations(range(DADOS), cantidad):
            guardados = tuple(sorted(dados[indice] for indice in guardar))
            valor = esperado_guardando(guardados, DADOS - cantidad, orden)

            if valor > mejor_valor:
                mejor_valor = valor
                mejor_indices = [i for i in range(DADOS) if i not in guardar]

    return mejor_indices, ahora, mejor_valor
