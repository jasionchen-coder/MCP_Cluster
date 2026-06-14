from sqlalchemy import text

from app.shared.database import create_session_maker, init_db


async def test_init_db_creates_base_tables(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

    engine, session_maker = create_session_maker(db_url)
    await init_db(engine)

    async with session_maker() as session:
        result = await session.execute(text("select 1"))

    assert result.scalar_one() == 1
