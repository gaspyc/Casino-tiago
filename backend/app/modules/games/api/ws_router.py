from fastapi import APIRouter

from app.modules.games.blackjack.multiplayer_router import router as blackjack_multiplayer_router

router = APIRouter(prefix="/games")
router.include_router(blackjack_multiplayer_router)

__all__ = ["router"]
