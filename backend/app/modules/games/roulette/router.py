from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.roulette.schemas import GameResultResponse, RouletteBetCreate
from app.modules.games.roulette.service import play_roulette_service
from app.modules.users.infrastructure.models import User
from app.shared.database import get_db
from app.shared.dependencies import get_current_user

router = APIRouter(prefix="/roulette", tags=["Roulette"])


@router.post("/bet", response_model=GameResultResponse)
async def play_roulette(
    bet_data: RouletteBetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await play_roulette_service(db, current_user.id, bet_data)
