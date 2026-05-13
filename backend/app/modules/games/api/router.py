from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.shared.database import get_db
from app.shared.dependencies import get_current_user
from app.modules.users.infrastructure.models import User
from app.modules.games.domain.entities import RouletteBetCreate, GameResultResponse, SlotBetCreate, SlotResultResponse, BlackjackBetCreate, BlackjackAction, BlackjackResponse
from app.modules.games.application.services import play_roulette_service

router = APIRouter(prefix="/games", tags=["Games"])

@router.get("/")
async def list_games():
    return [
        {"id": "roulette", "name": "European Roulette", "category": "Table"},
        {"id": "slots", "name": "Classic Slots", "category": "Slots"},
        {"id": "blackjack", "name": "Blackjack", "category": "Cards"}
    ]

@router.post("/roulette/bet", response_model=GameResultResponse)
async def play_roulette(bet_data: RouletteBetCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Jugar a la Ruleta Europea. Requiere Autenticación Bearer Token.
    """
    result = await play_roulette_service(db, current_user.id, bet_data)
    return result

@router.post("/slots/spin", response_model=SlotResultResponse)
async def play_slots(bet_data: SlotBetCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Ejecuta una tirada en la máquina tragamonedas."""
    from app.modules.games.application.services import play_slots_service
    result = await play_slots_service(db, current_user.id, bet_data)
    return result

@router.post("/blackjack/start", response_model=BlackjackResponse)
async def start_blackjack(bet_data: BlackjackBetCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.modules.games.application.blackjack_service import start_blackjack_service
    result = await start_blackjack_service(db, current_user.id, bet_data)
    return result

@router.post("/blackjack/hit", response_model=BlackjackResponse)
async def hit_blackjack(action: BlackjackAction, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.modules.games.application.blackjack_service import hit_blackjack_service
    result = await hit_blackjack_service(db, current_user.id, action)
    return result

@router.post("/blackjack/stand", response_model=BlackjackResponse)
async def stand_blackjack(action: BlackjackAction, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.modules.games.application.blackjack_service import stand_blackjack_service
    result = await stand_blackjack_service(db, current_user.id, action)
    return result

@router.post("/blackjack/double", response_model=BlackjackResponse)
async def double_blackjack(action: BlackjackAction, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.modules.games.application.blackjack_service import double_blackjack_service
    result = await double_blackjack_service(db, current_user.id, action)
    return result

@router.post("/blackjack/split", response_model=BlackjackResponse)
async def split_blackjack(action: BlackjackAction, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.modules.games.application.blackjack_service import split_blackjack_service
    result = await split_blackjack_service(db, current_user.id, action)
    return result
