"""Provably fair para el blackjack.

El mazo de 52 se mezcla con el Fisher-Yates verificable de `shared/mezcla.py`:

    bytes = HMAC_SHA256(server_seed, "client_seed:nonce:contador")

El servidor publica el SHA-256 del server seed antes de la primera mano y lo
revela cuando el jugador rota la semilla. Con el seed revelado cualquiera rehace
el mazo de cada mano que jugó, nonce por nonce, y comprueba que las cartas que
le tocaron son las que estaban arriba.

Por qué importa acá más que en otros juegos: el blackjack guarda el mazo que
queda en la fila de la partida. Mientras ese orden salía de `rng.shuffle`, el
jugador no tenía forma de saber si las cartas se mezclaron antes de la mano o se
fueron eligiendo sobre la marcha según cómo le estaba yendo. Ahora el mazo
entero queda fijado por el compromiso, antes de que se reparta la primera carta.

El orden del mazo sin mezclar es el que `MAZO` declara, y tiene que quedar
quieto: cambiarlo haría irreproducibles las manos ya jugadas.
"""

from app.modules.games.shared.mezcla import mezclar
from app.modules.games.shared.semillas import (
    generar_client_seed,
    generar_server_seed,
    hashear_seed,
)

__all__ = [
    "MAZO",
    "PALOS",
    "VALORES",
    "generar_client_seed",
    "generar_server_seed",
    "hashear_seed",
    "mezclar_mazo",
]

PALOS = ["♠", "♥", "♦", "♣"]
VALORES = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

# Palo por palo, como repartiría un mazo recién abierto.
MAZO = tuple("%s%s" % (valor, palo) for palo in PALOS for valor in VALORES)


def mezclar_mazo(server_seed: str, client_seed: str, nonce: int) -> list:
    """El mazo de una mano. Determinístico y verificable.

    La primera carta de la lista es la primera que se reparte.
    """
    return mezclar(MAZO, server_seed, client_seed, nonce)
