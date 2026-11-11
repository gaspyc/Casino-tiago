from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.modules.wallet.domain.entities import TransactionCreate
from app.modules.wallet.infrastructure.models import Transaction
from app.modules.wallet.application.balance import credit, debit

async def deposit_funds_service(db: AsyncSession, user_id: int, data: TransactionCreate) -> Transaction:
    if not await credit(db, user_id, data.amount):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    new_transaction = Transaction(
        user_id=user_id,
        amount=data.amount,
        transaction_type="DEPOSIT",
        status="COMPLETED"
    )
    db.add(new_transaction)
    
    await db.commit()
    await db.refresh(new_transaction)
    return new_transaction

async def withdraw_funds_service(db: AsyncSession, user_id: int, data: TransactionCreate) -> Transaction:
    if not await debit(db, user_id, data.amount):
        raise HTTPException(status_code=400, detail="Saldo insuficiente en la billetera")

    new_transaction = Transaction(
        user_id=user_id,
        amount=data.amount,
        transaction_type="WITHDRAW",
        status="COMPLETED"
    )
    db.add(new_transaction)
    
    await db.commit()
    await db.refresh(new_transaction)
    return new_transaction

async def get_transaction_history_service(db: AsyncSession, user_id: int):
    stmt = select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.created_at.desc()).limit(50)
    result = await db.execute(stmt)
    return result.scalars().all()
