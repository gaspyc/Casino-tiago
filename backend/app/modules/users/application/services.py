from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from app.modules.users.domain.entities import UserCreate
from app.modules.users.infrastructure.models import User
from app.shared.security import get_password_hash, verify_password

async def register_user_service(db: AsyncSession, user_in: UserCreate) -> User:
    query = select(User).where((User.email == user_in.email) | (User.username == user_in.username))
    result = await db.execute(query)
    existing_user = result.scalars().first()
    
    if existing_user:
        if existing_user.email == user_in.email:
            raise HTTPException(status_code=400, detail="El email ya está registrado")
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso")

    new_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        balance=0.00
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    user = result.scalars().first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
