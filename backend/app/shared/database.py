# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import declarative_base
from app.shared.config import settings

engine = create_async_engine(
    settings.async_database_url,
    echo=True,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
