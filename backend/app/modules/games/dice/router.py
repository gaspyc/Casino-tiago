from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.games.dice.service import (
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

router = APIRouter(prefix="/dice", tags=["Dice"])

Lado = Literal["menor", "mayor"]


class ApuestaDice(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)
    objetivo: Decimal = Field(..., ge=0, le=Decimal("99.99"))
    lado: Lado = "menor"


class RotarSemilla(BaseModel):
    client_seed: Optional[str] = Field(default=None, max_length=64)


@router.get("/limites")
async def ver_limites():
    """Los extremos que se pueden apostar y cuánto paga cada uno."""
    return tabla_de_limites()


@router.get("/cotizar")
async def ver_cotizacion(
    objetivo: Decimal,
    lado: Lado = "menor",
    current_user: User = Depends(get_current_user),
):
    """Qué paga esta apuesta, sin jugarla.

    La pantalla no calcula el multiplicador por su cuenta: lo pide. Así no
    puede quedar mostrando un pago distinto del que se liquida.
    """
    return cotizar(objetivo, lado)


@router.post("/apostar")
async def apostar(
    datos: ApuestaDice,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await jugar(db, current_user.id, datos.bet_amount, datos.objetivo, datos.lado)


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
