from decimal import Decimal

from pydantic import BaseModel, Field


class GeneralaEmpezar(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)


class GeneralaAccion(BaseModel):
    """Una acción del turno: "tirar:0,2,4" o "anotar:escalera"."""

    accion: str = Field(..., max_length=40)
