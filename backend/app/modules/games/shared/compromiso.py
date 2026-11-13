"""El ciclo de vida de las semillas provably fair, igual para todos los juegos.

El esquema es siempre el mismo: el servidor se compromete a un seed publicando
su SHA-256 antes de que se juegue, cada jugada consume un nonce, y al rotar la
semilla se revela el seed para que el jugador rehaga todas las jugadas que hizo
con ella. El client seed de la semilla nueva lo elige él, así el operador no
puede preparar el resultado de antemano.

Esto vivía dentro de `plinko/service.py`. Está acá porque lo único que cambia
entre juegos es el `game_id`, y la tabla `game_seeds` ya era multi-juego: tiene
un índice único parcial sobre (user_id, game_id) con revealed_at IS NULL, que
es lo que garantiza una sola semilla activa por jugador y juego.
"""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.modules.games.infrastructure.models import GameSeed
from app.modules.games.shared.semillas import (
    generar_client_seed,
    generar_server_seed,
    hashear_seed,
)

__all__ = [
    "describir_semilla",
    "obtener_semilla_activa",
    "rotar_semilla",
    "semilla_por_id",
    "siguiente_nonce",
]


def _consulta_activa(user_id: int, game_id: str):
    return (
        select(GameSeed)
        .where(
            GameSeed.user_id == user_id,
            GameSeed.game_id == game_id,
            GameSeed.revealed_at.is_(None),
        )
        .limit(1)
    )


async def obtener_semilla_activa(
    db: AsyncSession,
    user_id: int,
    game_id: str,
) -> GameSeed:
    """La semilla vigente del jugador, creándola en la primera jugada.

    Mientras está activa sólo se publica su hash.
    """
    consulta = _consulta_activa(user_id, game_id)

    semilla = await db.scalar(consulta)
    if semilla is not None:
        return semilla

    semilla = GameSeed(
        user_id=user_id,
        game_id=game_id,
        server_seed=generar_server_seed(),
        client_seed=generar_client_seed(),
        nonce=0,
    )
    semilla.server_seed_hash = hashear_seed(semilla.server_seed)
    db.add(semilla)

    try:
        await db.commit()
    except IntegrityError:
        # Dos jugadas simultáneas en la primera: el índice único deja una sola
        # semilla activa, así que la otra se queda con la que ganó.
        await db.rollback()
        semilla = await db.scalar(consulta)
        if semilla is None:
            raise

        return semilla

    await db.refresh(semilla)
    return semilla


async def semilla_por_id(db: AsyncSession, seed_id: int) -> GameSeed:
    """La semilla con la que se jugó una mano, aunque ya esté revelada.

    Los juegos que no resuelven en una sola jugada la necesitan después, para
    rehacer el tablero mientras la partida sigue abierta.
    """
    return await db.get(GameSeed, seed_id)


async def siguiente_nonce(db: AsyncSession, semilla: GameSeed) -> int:
    """Reserva el nonce de la jugada incrementándolo en la base.

    Tiene que ser en la base y no en Python: dos jugadas simultáneas que se
    quedaran con el mismo nonce darían el mismo resultado y romperían la
    verificación.
    """
    return await db.scalar(
        update(GameSeed)
        .where(GameSeed.id == semilla.id)
        .values(nonce=GameSeed.nonce + 1)
        .returning(GameSeed.nonce)
        .execution_options(synchronize_session=False)
    )


async def rotar_semilla(
    db: AsyncSession,
    user_id: int,
    game_id: str,
    client_seed: str = None,
) -> dict:
    """Revela la semilla vigente y deja una nueva activa.

    Con el seed revelado el jugador rehace todas las jugadas que hizo con esa
    semilla, nonce por nonce, y comprueba que el hash que vio desde el principio
    es el de ese seed.
    """
    anterior = await obtener_semilla_activa(db, user_id, game_id)
    anterior.revealed_at = func.now()

    nueva = GameSeed(
        user_id=user_id,
        game_id=game_id,
        server_seed=generar_server_seed(),
        client_seed=client_seed or generar_client_seed(),
        nonce=0,
    )
    nueva.server_seed_hash = hashear_seed(nueva.server_seed)
    db.add(nueva)

    await db.commit()
    await db.refresh(anterior)
    await db.refresh(nueva)

    return {
        "revelada": {
            "server_seed": anterior.server_seed,
            "server_seed_hash": anterior.server_seed_hash,
            "client_seed": anterior.client_seed,
            "jugadas": anterior.nonce,
        },
        "activa": describir_semilla(nueva),
    }


def describir_semilla(semilla: GameSeed) -> dict:
    """Lo único que se publica de una semilla activa: su compromiso."""
    return {
        "server_seed_hash": semilla.server_seed_hash,
        "client_seed": semilla.client_seed,
        "nonce": semilla.nonce,
    }
