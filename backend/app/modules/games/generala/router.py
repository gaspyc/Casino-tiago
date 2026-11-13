from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.generala.dados import (
    CATEGORIAS,
    PUNTAJE_ARMADA,
    PUNTAJE_SERVIDA,
)
from app.modules.games.generala.schemas import GeneralaAccion, GeneralaEmpezar
from app.modules.games.generala.service import (
    APUESTA_MAXIMA,
    MULTIPLICADOR_DE_PAGO,
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
        "generala_servida_gana": True,
        "apuesta_maxima": str(APUESTA_MAXIMA),
        "multiplicador": str(MULTIPLICADOR_DE_PAGO),
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
