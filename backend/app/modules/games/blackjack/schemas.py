from decimal import Decimal

from pydantic import BaseModel, Field


class BlackjackBetCreate(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)


class BlackjackAction(BaseModel):
    game_id: int


class BlackjackResponse(BaseModel):
    game_id: int
    bet_amount: Decimal
    status: str
    player_hand: list
    dealer_hand: list
    player_score: list | int
    dealer_score: int
    net_profit: Decimal
    total_payout: Decimal
    is_split: bool = False
    active_hand_index: int = 0
