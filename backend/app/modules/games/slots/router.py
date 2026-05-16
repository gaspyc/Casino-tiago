from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.slots.schemas import SlotBetCreate, SlotResultResponse
from app.modules.games.slots.service import play_slots_service
from app.modules.users.infrastructure.models import User
from app.shared.database import get_db
from app.shared.dependencies import get_current_user

router = APIRouter(prefix="/slots", tags=["Slots"])


@router.post("/spin", response_model=SlotResultResponse)
async def play_slots(
    bet_data: SlotBetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await play_slots_service(db, current_user.id, bet_data)
