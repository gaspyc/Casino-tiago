from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.generala import mesas
from app.modules.games.generala.dados import (
    CATEGORIAS,
    PUNTAJE_ARMADA,
    PUNTAJE_SERVIDA,
)
from app.modules.games.generala.schemas import GeneralaAccion, GeneralaEmpezar
from app.modules.games.generala import pagos
from app.modules.games.generala.service import (
    APUESTA_MAXIMA,
    empezar_partida,
    jugar_accion,
    partida_abierta,
    reconstruir,
    _respuesta,
)
from app.modules.games.generala.turno import TIRADAS_POR_TURNO
from app.modules.users.infrastructure.models import User
from app.shared.database import get_db
from app.shared.dependencies import get_current_user

router = APIRouter(prefix="/generala", tags=["Generala"])


@router.get("/reglas")
async def ver_reglas():
    """Las reglas que se juegan acá, que no son las mismas en todas las mesas."""
    return {
        "categorias": list(CATEGORIAS),
        "tiradas_por_turno": TIRADAS_POR_TURNO,
        "puntaje_armada": PUNTAJE_ARMADA,
        "puntaje_servida": PUNTAJE_SERVIDA,
        "escaleras": ["1-2-3-4-5", "2-3-4-5-6"],
        "apuesta_maxima": str(APUESTA_MAXIMA),
        # Contra la casa se cobra por puntaje, así que la servida no corta la
        # partida: se paga aparte. En la mesa entre jugadores sí corta, que es
        # la regla clásica.
        "generala_servida_gana": False,
        "paga_por_puntaje": True,
        "equilibrio": pagos.PUNTAJE_DE_EQUILIBRIO,
        "premio_servida": str(pagos.PREMIO_SERVIDA),
        "tabla": pagos.tabla_de_referencia(),
        "mesa_generala_servida_gana": True,
    }


@router.post("/partida")
async def empezar(
    datos: GeneralaEmpezar,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await empezar_partida(db, current_user.id, datos.bet_amount)


@router.get("/partida")
async def ver_partida(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """La partida sin terminar, para retomarla al volver."""
    fila = await partida_abierta(db, current_user.id)
    if fila is None:
        return None

    return _respuesta(fila, reconstruir(fila))


@router.post("/accion")
async def jugar(
    datos: GeneralaAccion,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await jugar_accion(db, current_user.id, datos.accion)


# ------------------------------ mesas entre jugadores ------------------------------


class MesaNueva(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)


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
    return await mesas.crear_mesa(db, current_user.id, datos.bet_amount)


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
    datos: GeneralaAccion,
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
