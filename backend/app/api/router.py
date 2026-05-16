from fastapi import APIRouter

from app.modules.games.api.router import router as games_router
from app.modules.users.api.router import router as users_router
from app.modules.wallet.api.router import router as wallet_router

api_router = APIRouter()

api_router.include_router(users_router)
api_router.include_router(wallet_router)
api_router.include_router(games_router)
