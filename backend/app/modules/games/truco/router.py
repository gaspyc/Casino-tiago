from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.truco.service import (
    empezar_partida,
    jugar_accion,
    partida_abierta,
    reconstruir,
    _respuesta,
)
from app.modules.users.infrastructure.models import User
from app.shared.database import get_db
from app.shared.dependencies import get_current_user

router = APIRouter(prefix="/truco", tags=["Truco"])


class ApuestaTruco(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)


class AccionTruco(BaseModel):
    accion: str = Field(..., max_length=32)


@router.post("/partida")
async def empezar(
    datos: ApuestaTruco,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apuesta y reparte la primera mano."""
    return await empezar_partida(db, current_user.id, datos.bet_amount)


@router.get("/partida")
async def ver_partida(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """La partida abierta del jugador, para retomarla donde quedó."""
    fila = await partida_abierta(db, current_user.id)
    if fila is None:
        raise HTTPException(status_code=404, detail="No tenés una partida abierta")

    return _respuesta(fila, reconstruir(fila))


@router.post("/accion")
async def jugar(
    datos: AccionTruco,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Juega una carta o canta, y después juega la casa hasta que te toque."""
    return await jugar_accion(db, current_user.id, datos.accion)
