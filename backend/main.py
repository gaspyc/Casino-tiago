# pyrefly: ignore [missing-import]
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.shared.config import settings
from app.shared.database import engine, Base

# Importar modelos para que SQLAlchemy los detecte al hacer create_all
from app.modules.users.infrastructure.models import User
from app.modules.wallet.infrastructure.models import Transaction
from app.modules.games.infrastructure.models import Bet

from app.modules.games.crash.service import crash_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ya no usamos Base.metadata.create_all, Alembic maneja las migraciones.
    crash_manager.start_loop()
    yield

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

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Welcome to the Online Casino API"}
