from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.limbo.service import (
    cotizar,
    describir_semilla,
    jugar,
    obtener_semilla_activa,
    rotar_semilla,
    tabla_de_limites,
)
from app.modules.users.infrastructure.models import User
from app.shared.database import get_db
from app.shared.dependencies import get_current_user

router = APIRouter(prefix="/limbo", tags=["Limbo"])


class ApuestaLimbo(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)
    objetivo: Decimal = Field(..., ge=Decimal("1.01"), le=Decimal("1000.00"))


class RotarSemilla(BaseModel):
    client_seed: Optional[str] = Field(default=None, max_length=64)


@router.get("/limites")
async def ver_limites():
    return tabla_de_limites()


@router.get("/cotizar")
async def ver_cotizacion(
    objetivo: Decimal,
    current_user: User = Depends(get_current_user),
):
    """La chance de este objetivo, sin jugarlo."""
    return cotizar(objetivo)


@router.post("/apostar")
async def apostar(
    datos: ApuestaLimbo,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await jugar(db, current_user.id, datos.bet_amount, datos.objetivo)


@router.get("/semilla")
async def obtener_compromiso(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """El compromiso de la semilla vigente: su hash, antes de jugar."""
    semilla = await obtener_semilla_activa(db, current_user.id)
    return describir_semilla(semilla)


@router.post("/semilla/rotar")
async def rotar_compromiso(
    datos: RotarSemilla = RotarSemilla(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revela la semilla vigente y deja una nueva, para poder verificar."""
    return await rotar_semilla(db, current_user.id, datos.client_seed)
