from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean
from sqlalchemy.sql import func
from app.shared.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    balance = Column(Numeric(10, 2), default=0.00, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
