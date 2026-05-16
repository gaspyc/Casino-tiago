from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.blackjack.schemas import BlackjackAction, BlackjackBetCreate, BlackjackResponse
from app.modules.games.blackjack.service import (
    double_blackjack_service,
    hit_blackjack_service,
    split_blackjack_service,
    stand_blackjack_service,
    start_blackjack_service,
)
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
