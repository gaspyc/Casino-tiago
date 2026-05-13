# pyrefly: ignore [missing-import]
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.shared.config import settings
from app.shared.database import engine, Base

# Importar modelos para que SQLAlchemy los detecte al hacer create_all
from app.modules.users.infrastructure.models import User
from app.modules.wallet.infrastructure.models import Transaction
from app.modules.games.infrastructure.models import Bet

from app.modules.users.api.router import router as users_router
from app.modules.wallet.api.router import router as wallet_router
from app.modules.games.api.router import router as games_router
from app.modules.games.api.ws_router import router as ws_blackjack_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ya no usamos Base.metadata.create_all, Alembic maneja las migraciones.
    yield

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permitir frontend desde Vite (localhost:5173 o cualquiera)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(wallet_router, prefix=settings.API_V1_STR)
app.include_router(games_router, prefix=settings.API_V1_STR)
app.include_router(ws_blackjack_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Welcome to the Online Casino API"}
