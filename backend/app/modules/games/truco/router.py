from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.truco import mesas
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
    con_flor: bool = False


class AccionTruco(BaseModel):
    accion: str = Field(..., max_length=32)


@router.post("/partida")
async def empezar(
    datos: ApuestaTruco,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apuesta y reparte la primera mano."""
    return await empezar_partida(db, current_user.id, datos.bet_amount, datos.con_flor)


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


# ------------------------------ mesas entre jugadores ------------------------------


class MesaNueva(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)
    con_flor: bool = False


@router.get("/mesas")
async def listar_mesas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Las mesas abiertas, para sentarse en una."""
    mia = await mesas.mesa_del_jugador(db, current_user.id)

    return {
        "mesas": await mesas.listar_mesas(db, current_user.id),
        "mi_mesa": mia.id if mia is not None else None,
        "comision": str(mesas.COMISION),
        "plazo_de_turno": int(mesas.PLAZO_DE_TURNO.total_seconds()),
        "apuesta_maxima": str(mesas.APUESTA_MAXIMA),
    }


@router.post("/mesas")
async def crear_mesa(
    datos: MesaNueva,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crea una mesa y deja la apuesta puesta esperando rival."""
    return await mesas.crear_mesa(db, current_user.id, datos.bet_amount, datos.con_flor)


@router.post("/mesas/{mesa_id}/sentarse")
async def sentarse(
    mesa_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await mesas.sentarse(db, current_user.id, mesa_id)


@router.get("/mesas/{mesa_id}")
async def ver_mesa(
    mesa_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """El estado de la mesa. El cliente lo consulta cada par de segundos."""
    return await mesas.ver_mesa(db, current_user.id, mesa_id)


@router.post("/mesas/{mesa_id}/accion")
async def jugar_en_mesa(
    mesa_id: int,
    datos: AccionTruco,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await mesas.jugar(db, current_user.id, mesa_id, datos.accion)


@router.post("/mesas/{mesa_id}/reclamar")
async def reclamar_mesa(
    mesa_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Se lleva la mesa porque al rival se le venció el plazo del turno."""
    return await mesas.reclamar(db, current_user.id, mesa_id)


@router.post("/mesas/{mesa_id}/abandonar")
async def abandonar_mesa(
    mesa_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Se va de la mesa. Si todavía nadie se sentó, se devuelve la apuesta."""
    return await mesas.abandonar(db, current_user.id, mesa_id)
