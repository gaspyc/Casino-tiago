from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Literal, List

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

class SlotBetCreate(BaseModel):
    bet_amount: Decimal = Field(..., gt=0, decimal_places=2)

class SlotResultResponse(BaseModel):
    game_id: str
    bet_amount: Decimal
    total_payout: Decimal
    net_profit: Decimal
    result_data: dict

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
