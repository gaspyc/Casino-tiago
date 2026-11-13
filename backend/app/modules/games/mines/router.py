from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.mines.paytable import (
    APUESTA_MAXIMA,
    APUESTA_MINIMA,
    CASILLAS,
    MAX_MINAS,
    MIN_MINAS,
    RTP,
    tabla_de_multiplicadores,
)
from app.modules.games.mines.schemas import (
    MinesDestapar,
    MinesEmpezar,
    MinesEstado,
    MinesRotarSeed,
)
from app.modules.games.mines.service import (
    cobrar,
    destapar,
    empezar,
    obtener_semilla_mines,
    rotar_semilla_mines,
    ver_activa,
)
from app.modules.games.shared.compromiso import describir_semilla
from app.modules.users.infrastructure.models import User
from app.shared.database import get_db
from app.shared.dependencies import get_current_user

router = APIRouter(prefix="/mines", tags=["Mines"])


@router.get("/tabla")
async def ver_tabla():
    """Los pagos de cada cantidad de minas. No hace falta estar jugando.

    Se publican enteros a propósito: son el precio del juego y el jugador los
    puede recalcular con la fórmula hipergeométrica antes de apostar.
    """
    return {
        "casillas": CASILLAS,
        "min_minas": MIN_MINAS,
        "max_minas": MAX_MINAS,
        "apuesta_minima": str(APUESTA_MINIMA),
        "apuesta_maxima": str(APUESTA_MAXIMA),
        "rtp": str(round(float(RTP) * 100, 2)),
        "multiplicadores": {
            minas: [str(valor) for valor in tabla_de_multiplicadores(minas)]
            for minas in range(MIN_MINAS, MAX_MINAS + 1)
        },
    }


@router.post("/empezar", response_model=MinesEstado)
async def empezar_grilla(
    datos: MinesEmpezar,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await empezar(db, current_user.id, datos.bet_amount, datos.minas)


@router.post("/destapar", response_model=MinesEstado)
async def destapar_casilla(
    datos: MinesDestapar,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await destapar(db, current_user.id, datos.casilla)


@router.post("/cobrar", response_model=MinesEstado)
async def cobrar_grilla(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await cobrar(db, current_user.id)


@router.get("/activa", response_model=MinesEstado | None)
async def ver_grilla_activa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """La grilla sin terminar del jugador, para retomarla al volver."""
    return await ver_activa(db, current_user.id)


@router.get("/semilla")
async def ver_compromiso(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """El compromiso de la semilla vigente: su hash, antes de jugar."""
    semilla = await obtener_semilla_mines(db, current_user.id)
    return describir_semilla(semilla)


@router.post("/semilla/rotar")
async def rotar_compromiso(
    datos: MinesRotarSeed,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revela la semilla vigente y deja una nueva.

    Con el seed revelado el jugador rehace el tablero de todas las grillas que
    jugó con esa semilla, nonce por nonce, y comprueba que la mina que lo mató
    ya estaba ahí desde antes del primer destape.
    """
    return await rotar_semilla_mines(db, current_user.id, datos.client_seed)
