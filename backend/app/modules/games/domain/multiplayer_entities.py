from typing import List, Optional
from pydantic import BaseModel
from decimal import Decimal

class TableResponse(BaseModel):
    id: int
    name: str
    status: str
    player_count: int

class MultiplayerAction(BaseModel):
    action: str # "join", "bet", "hit", "stand", "double", "split"
    bet_amount: Optional[Decimal] = None
