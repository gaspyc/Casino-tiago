from pydantic import BaseModel


class TableResponse(BaseModel):
    id: int
    name: str
    status: str
    player_count: int


class MultiplayerAction(BaseModel):
    action: str
    payload: dict = {}
