from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, Field


class RouletteBetItem(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)
    bet_type: Literal["number", "color", "parity", "split", "corner"]
    bet_value: str


class RouletteBetCreate(BaseModel):
    bets: List[RouletteBetItem] = Field(..., min_length=1)


class BetResultDetail(BaseModel):
    bet_type: str
    bet_value: str
    bet_amount: Decimal
    payout: Decimal
    win: bool


class GameResultResponse(BaseModel):
    game_id: str
    total_bet_amount: Decimal
    total_payout: Decimal
    net_profit: Decimal
    result_data: dict
    bet_details: List[BetResultDetail]
