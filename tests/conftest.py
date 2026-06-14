import asyncio
import os

import pytest

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.shared.database import Base, engine


async def _reset_database() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
def reset_database():
    asyncio.run(_reset_database())
