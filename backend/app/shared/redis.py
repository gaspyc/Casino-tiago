"""Cliente Redis compartido.

Redis coordina el juego de Crash entre procesos: cuál corre el game loop, el
estado de la ronda en curso y el fan-out de los eventos a los WebSockets que
atiende cada worker.
"""

from typing import Optional

from redis.asyncio import Redis

from app.shared.config import settings

_cliente: Optional[Redis] = None


def get_redis() -> Redis:
    """Cliente único del proceso. `decode_responses` para trabajar con str."""
    global _cliente
    if _cliente is None:
        _cliente = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _cliente


async def cerrar_redis() -> None:
    global _cliente
    if _cliente is not None:
        await _cliente.aclose()
        _cliente = None
