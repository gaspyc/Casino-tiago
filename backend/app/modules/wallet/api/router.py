from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.shared.database import get_db
from app.shared.dependencies import get_current_user
from app.modules.users.infrastructure.models import User
from app.modules.wallet.domain.entities import TransactionCreate, TransactionResponse
from app.modules.wallet.application.services import deposit_funds_service, withdraw_funds_service

router = APIRouter(prefix="/wallet", tags=["Wallet"])

@router.get("/balance")
async def get_my_balance(current_user: User = Depends(get_current_user)):
    return {"user_id": current_user.id, "balance": current_user.balance, "currency": "USD"}

@router.post("/deposit", response_model=TransactionResponse)
async def deposit_funds(data: TransactionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    transaction = await deposit_funds_service(db, current_user.id, data)
    return transaction

@router.post("/withdraw", response_model=TransactionResponse)
async def withdraw_funds(data: TransactionCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    transaction = await withdraw_funds_service(db, current_user.id, data)
    return transaction

@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transaction_history(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Obtiene el historial de las últimas 50 transacciones del usuario."""
    from app.modules.wallet.application.services import get_transaction_history_service
    transactions = await get_transaction_history_service(db, current_user.id)
    return transactions
