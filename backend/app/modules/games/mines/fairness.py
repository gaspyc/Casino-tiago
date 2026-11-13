"""Provably fair para el mines.

Las minas se ubican antes del primer destape, con el mismo Fisher-Yates
verificable que usan el truco y el blackjack:

    orden = mezclar([0..24], server_seed, client_seed, nonce)
    minas = las primeras `minas` posiciones de ese orden

Lo que esto garantiza es justo lo que un jugador sospecha de un buscaminas de
casino: que la mina no se pone donde él toca. El tablero queda fijado por el
compromiso antes de que destape nada, y al revelar el seed se comprueba que la
mina que lo mató ya estaba ahí.

Por eso el orden entero se guarda, y no sólo las posiciones de las minas: con
el orden completo la verificación es una línea, sin reconstruir conjuntos.
"""

from app.modules.games.mines.paytable import CASILLAS
from app.modules.games.shared.mezcla import mezclar

__all__ = ["orden_del_tablero", "posiciones_de_minas"]


def orden_del_tablero(server_seed: str, client_seed: str, nonce: int) -> list:
    """Las 25 casillas barajadas. Determinístico y verificable."""
    return mezclar(range(CASILLAS), server_seed, client_seed, nonce)


def posiciones_de_minas(
    server_seed: str,
    client_seed: str,
    nonce: int,
    minas: int,
) -> set:
    """Dónde quedaron las minas de esta grilla."""
    return set(orden_del_tablero(server_seed, client_seed, nonce)[:minas])
