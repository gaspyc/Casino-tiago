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

    # El compromiso de la mano: el hash ya estaba publicado antes del reparto.
    # None en las manos repartidas antes de que el blackjack fuera verificable.
    server_seed_hash: str | None = None
    client_seed: str | None = None
    nonce: int | None = None


class BlackjackRotarSeed(BaseModel):
    """El jugador elige el client seed de la semilla nueva."""

    client_seed: str | None = Field(None, max_length=64)
