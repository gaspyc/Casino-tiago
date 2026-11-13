"""Reparto verificable para el truco.

El mazo se mezcla con el Fisher-Yates de `shared/mezcla.py`, manejado por los
bytes de un HMAC, así que el reparto de una mano queda determinado por el seed y
se puede rehacer después, igual que el camino de la bola en plinko.
"""

from app.modules.games.shared.mezcla import mezclar as _mezclar
from app.modules.games.shared.semillas import generar_server_seed, hashear_seed
from app.modules.games.truco.cartas import MAZO

__all__ = ["generar_server_seed", "hashear_seed", "mezclar", "repartir"]

CARTAS_POR_JUGADOR = 3


def mezclar(server_seed: str, client_seed: str, nonce: int) -> list:
    """El mazo mezclado de una mano. Determinístico y verificable."""
    return _mezclar(MAZO, server_seed, client_seed, nonce)


def repartir(server_seed: str, client_seed: str, nonce: int, jugadores: int = 2) -> list:
    """Reparte de a una carta por jugador, como en la mesa."""
    mazo = mezclar(server_seed, client_seed, nonce)
    manos = [[] for _ in range(jugadores)]

    for vuelta in range(CARTAS_POR_JUGADOR):
        for jugador in range(jugadores):
            manos[jugador].append(mazo[vuelta * jugadores + jugador])

    return manos
