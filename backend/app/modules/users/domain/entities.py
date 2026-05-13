from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from decimal import Decimal

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., max_length=72, description="La contraseña no puede exceder 72 caracteres debido a límites de seguridad (Bcrypt)")

class UserResponse(UserBase):
    id: int
    balance: Decimal
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
