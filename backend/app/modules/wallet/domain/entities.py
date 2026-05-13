from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal

from typing import Optional

class TransactionBase(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2, description="Monto mayor a cero con hasta 2 decimales")

class TransactionCreate(TransactionBase):
    pass # Ya no necesitamos user_id porque vendrá del JWT

class TransactionResponse(TransactionBase):
    id: int
    user_id: int
    transaction_type: str
    status: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
