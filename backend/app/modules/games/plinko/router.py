from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.plinko.schemas import PlinkoBetCreate, PlinkoResultResponse
from app.modules.games.plinko.service import play_plinko_service
from app.modules.users.infrastructure.models import User
from app.shared.database import get_db
from app.shared.dependencies import get_current_user

router = APIRouter(prefix="/plinko", tags=["Plinko"])


@router.post("/drop", response_model=PlinkoResultResponse)
async def drop_plinko_ball(
    bet_data: PlinkoBetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await play_plinko_service(db, current_user.id, bet_data)
