"""Reparto verificable para el truco.

El mazo se mezcla con un Fisher-Yates manejado por los bytes de un HMAC, así
que el reparto de una mano queda determinado por el seed y se puede rehacer
después, igual que el camino de la bola en plinko.

    bytes = HMAC_SHA256(server_seed, "client_seed:nonce:contador")

Los índices salen por muestreo con rechazo: tomar el byte módulo el tope daría
ventaja a las primeras posiciones, porque 256 no es múltiplo de 40.
"""

import hashlib
import hmac

from app.modules.games.shared.semillas import generar_server_seed, hashear_seed
from app.modules.games.truco.cartas import MAZO

__all__ = ["generar_server_seed", "hashear_seed", "mezclar", "repartir"]

CARTAS_POR_JUGADOR = 3


def _flujo_de_bytes(server_seed: str, client_seed: str, nonce: int):
    contador = 0
    while True:
        bloque = hmac.new(
            server_seed.encode(),
            ("%s:%s:%s" % (client_seed, nonce, contador)).encode(),
            hashlib.sha256,
        ).digest()

        for byte in bloque:
            yield byte

        contador += 1


def _indice(flujo, tope: int) -> int:
    """Entero uniforme en [0, tope) descartando los bytes que sesgarían."""
    limite = 256 - (256 % tope)

    for byte in flujo:
        if byte < limite:
            return byte % tope

    raise RuntimeError("El flujo de bytes se agotó")


def mezclar(server_seed: str, client_seed: str, nonce: int) -> list:
    """El mazo mezclado de una mano. Determinístico y verificable."""
    mazo = list(MAZO)
    flujo = _flujo_de_bytes(server_seed, client_seed, nonce)

    for posicion in range(len(mazo) - 1, 0, -1):
        otra = _indice(flujo, posicion + 1)
        mazo[posicion], mazo[otra] = mazo[otra], mazo[posicion]

    return mazo


def repartir(server_seed: str, client_seed: str, nonce: int, jugadores: int = 2) -> list:
    """Reparte de a una carta por jugador, como en la mesa."""
    mazo = mezclar(server_seed, client_seed, nonce)
    manos = [[] for _ in range(jugadores)]

    for vuelta in range(CARTAS_POR_JUGADOR):
        for jugador in range(jugadores):
            manos[jugador].append(mazo[vuelta * jugadores + jugador])

    return manos
