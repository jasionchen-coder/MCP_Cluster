from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase

from app.shared.config import get_settings


class Base(DeclarativeBase):
    pass


def create_session_maker(database_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(database_url, future=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


engine, SessionLocal = create_session_maker(get_settings().database_url)


async def init_db(db_engine: AsyncEngine = engine) -> None:
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if db_engine.dialect.name == "postgresql":
            settings = get_settings()
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS embedding JSONB"))
            await conn.execute(
                text(
                    f"ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS embedding_vector vector({settings.rag_embedding_dimension})"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding_vector "
                    "ON rag_chunks USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100)"
                )
            )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
