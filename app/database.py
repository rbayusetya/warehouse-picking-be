from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    # Run Alembic migrations in a worker thread so the event loop is not blocked
    # during startup (uvicorn only needs the loop free once this coroutine ends).
    import asyncio
    from alembic.config import Config
    from alembic.command import upgrade

    def _run_migration():
        alembic_cfg = Config("alembic.ini")
        upgrade(alembic_cfg, "head")

    await asyncio.to_thread(_run_migration)
