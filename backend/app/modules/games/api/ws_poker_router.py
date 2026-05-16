from fastapi import APIRouter

from app.modules.games.poker.multiplayer_router import router as poker_multiplayer_router

router = APIRouter(prefix="/games")
router.include_router(poker_multiplayer_router)

__all__ = ["router"]
