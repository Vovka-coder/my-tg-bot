"""
RefLens — Database Session Factory
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",  # SQL-лог только в dev
    pool_size=20,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # объекты доступны после коммита
)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
