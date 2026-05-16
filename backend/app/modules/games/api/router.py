from fastapi import APIRouter

from app.modules.games.blackjack.multiplayer_router import router as blackjack_multiplayer_router
from app.modules.games.blackjack.router import router as blackjack_router
from app.modules.games.crash.router import router as crash_router
from app.modules.games.poker.multiplayer_router import router as poker_multiplayer_router
from app.modules.games.roulette.router import router as roulette_router
from app.modules.games.slots.router import router as slots_router

router = APIRouter(prefix="/games", tags=["Games"])


@router.get("/")
async def list_games():
    return [
        {"id": "roulette", "name": "European Roulette", "category": "Table"},
        {"id": "slots", "name": "Classic Slots", "category": "Slots"},
        {"id": "blackjack", "name": "Blackjack", "category": "Cards"},
        {"id": "poker", "name": "Poker", "category": "Cards"},
        {"id": "crash", "name": "Crash", "category": "Arcade"},
    ]


router.include_router(roulette_router)
router.include_router(slots_router)
router.include_router(blackjack_router)
router.include_router(blackjack_multiplayer_router)
router.include_router(poker_multiplayer_router)
router.include_router(crash_router)
