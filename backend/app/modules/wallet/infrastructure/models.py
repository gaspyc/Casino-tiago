from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.shared.database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    transaction_type = Column(String, nullable=False) # DEPOSIT, WITHDRAW, BET, PAYOUT
    status = Column(String, default="COMPLETED", nullable=False) # COMPLETED, FAILED, PENDING
    description = Column(String, nullable=True) # Nombre del juego u origen
    created_at = Column(DateTime(timezone=True), server_default=func.now())
