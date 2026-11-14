from fastapi import APIRouter

from app.modules.games.blackjack.multiplayer_router import router as blackjack_multiplayer_router
from app.modules.games.blackjack.router import router as blackjack_router
from app.modules.games.crash.router import router as crash_router
from app.modules.games.dice.router import router as dice_router
from app.modules.games.poker.multiplayer_router import router as poker_multiplayer_router
from app.modules.games.generala.router import router as generala_router
from app.modules.games.limbo.router import router as limbo_router
from app.modules.games.mines.router import router as mines_router
from app.modules.games.plinko.router import router as plinko_router
from app.modules.games.roulette.router import router as roulette_router
from app.modules.games.slots.router import router as slots_router
from app.modules.games.truco.router import router as truco_router

router = APIRouter(prefix="/games", tags=["Games"])


@router.get("/")
async def list_games():
    return [
        {"id": "roulette", "name": "European Roulette", "category": "Table"},
        {"id": "slots", "name": "Classic Slots", "category": "Slots"},
        {"id": "blackjack", "name": "Blackjack", "category": "Cards"},
        {"id": "poker", "name": "Poker", "category": "Cards"},
        {"id": "crash", "name": "Crash", "category": "Arcade"},
        {"id": "plinko", "name": "Plinko", "category": "Arcade"},
        {"id": "truco", "name": "Truco", "category": "Cards"},
        {"id": "dice", "name": "Dice", "category": "Arcade"},
        {"id": "limbo", "name": "Limbo", "category": "Arcade"},
    ]


router.include_router(roulette_router)
router.include_router(slots_router)
router.include_router(blackjack_router)
router.include_router(blackjack_multiplayer_router)
router.include_router(poker_multiplayer_router)
router.include_router(crash_router)
router.include_router(plinko_router)
router.include_router(mines_router)
router.include_router(generala_router)
router.include_router(truco_router)
router.include_router(dice_router)
router.include_router(limbo_router)
