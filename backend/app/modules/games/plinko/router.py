from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.plinko.schemas import PlinkoBetCreate, PlinkoResultResponse
from app.modules.games.plinko.service import (
    describir_semilla,
    obtener_semilla_activa,
    play_plinko_service,
    rotar_semilla,
)
from app.modules.users.infrastructure.models import User
from app.shared.database import get_db
from app.shared.dependencies import get_current_user

router = APIRouter(prefix="/plinko", tags=["Plinko"])


class RotarSemilla(BaseModel):
    client_seed: Optional[str] = Field(default=None, max_length=64)


@router.post("/drop", response_model=PlinkoResultResponse)
async def drop_plinko_ball(
    bet_data: PlinkoBetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await play_plinko_service(db, current_user.id, bet_data)


@router.get("/semilla")
async def obtener_compromiso(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """El compromiso de la semilla vigente: su hash, antes de jugar."""
    semilla = await obtener_semilla_activa(db, current_user.id)
    return describir_semilla(semilla)


@router.post("/semilla/rotar")
async def rotar_compromiso(
    datos: RotarSemilla = RotarSemilla(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revela la semilla vigente y deja una nueva.

    Devuelve el server seed revelado para que el jugador pueda rehacer el camino
    de todas las bolas que tiró con esa semilla.
    """
    return await rotar_semilla(db, current_user.id, datos.client_seed)
