from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.shared.database import get_db
from app.shared.security import create_access_token
from app.shared.dependencies import get_current_user
from app.modules.users.domain.entities import UserCreate, UserResponse
from app.modules.users.application.services import register_user_service, authenticate_user
from app.modules.users.infrastructure.models import User

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/register", response_model=UserResponse)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Registra un nuevo usuario en el sistema."""
    new_user = await register_user_service(db, user_in)
    return new_user

@router.post("/login")
async def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user
