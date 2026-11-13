from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.blackjack.schemas import (
    BlackjackAction,
    BlackjackBetCreate,
    BlackjackResponse,
    BlackjackRotarSeed,
)
from app.modules.games.blackjack.service import (
    double_blackjack_service,
    hit_blackjack_service,
    obtener_mano_activa,
    obtener_semilla_blackjack,
    rotar_semilla_blackjack,
    split_blackjack_service,
    stand_blackjack_service,
    start_blackjack_service,
)
from app.modules.games.shared.compromiso import describir_semilla
from app.modules.users.infrastructure.models import User
from app.shared.database import get_db
from app.shared.dependencies import get_current_user

router = APIRouter(prefix="/blackjack", tags=["Blackjack"])


@router.post("/start", response_model=BlackjackResponse)
async def start_blackjack(
    bet_data: BlackjackBetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await start_blackjack_service(db, current_user.id, bet_data)


@router.post("/hit", response_model=BlackjackResponse)
async def hit_blackjack(
    action: BlackjackAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await hit_blackjack_service(db, current_user.id, action)


@router.post("/stand", response_model=BlackjackResponse)
async def stand_blackjack(
    action: BlackjackAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await stand_blackjack_service(db, current_user.id, action)


@router.post("/double", response_model=BlackjackResponse)
async def double_blackjack(
    action: BlackjackAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await double_blackjack_service(db, current_user.id, action)


@router.post("/split", response_model=BlackjackResponse)
async def split_blackjack(
    action: BlackjackAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await split_blackjack_service(db, current_user.id, action)


@router.get("/activa", response_model=BlackjackResponse | None)
async def ver_mano_activa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """La mano sin terminar del jugador, para retomarla al volver."""
    return await obtener_mano_activa(db, current_user.id)


@router.get("/semilla")
async def ver_compromiso(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """El compromiso de la semilla vigente: su hash, antes de repartir."""
    semilla = await obtener_semilla_blackjack(db, current_user.id)
    return describir_semilla(semilla)


@router.post("/semilla/rotar")
async def rotar_compromiso(
    datos: BlackjackRotarSeed,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revela la semilla vigente y deja una nueva.

    Con el seed revelado el jugador rehace el mazo de todas las manos que jugó
    con esa semilla, nonce por nonce. No se puede con una mano abierta.
    """
    return await rotar_semilla_blackjack(db, current_user.id, datos.client_seed)
