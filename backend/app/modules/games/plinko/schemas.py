from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


PlinkoRisk = Literal["low", "medium", "high"]


class PlinkoBetCreate(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)
    risk: PlinkoRisk = "medium"
    rows: int = Field(12, ge=8, le=16)


class PlinkoResultResponse(BaseModel):
    game_id: str
    bet_amount: Decimal
    total_payout: Decimal
    net_profit: Decimal
    result_data: dict
