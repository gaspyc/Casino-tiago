from fastapi import APIRouter

from app.modules.games.crash.router import router as crash_router

router = APIRouter(prefix="/games")
router.include_router(crash_router)

__all__ = ["router"]
