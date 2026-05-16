from decimal import Decimal

from pydantic import BaseModel, Field


class SlotBetCreate(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)


class SlotResultResponse(BaseModel):
    game_id: str
    bet_amount: Decimal
    total_payout: Decimal
    net_profit: Decimal
    result_data: dict
