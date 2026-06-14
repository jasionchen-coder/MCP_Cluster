import asyncio

from sqlalchemy import text

from app.modules.rag_service.schemas import RagSearchRequest
from app.modules.rag_service.service import search
from app.shared.database import SessionLocal, engine, init_db
from scripts.seed_dev_data import seed_dev_data


async def check_pgvector() -> None:
    await init_db()
    await seed_dev_data()
    async with engine.connect() as conn:
        dialect = engine.dialect.name
        print("dialect", dialect)
        if dialect == "postgresql":
            extension = (
                await conn.execute(
                    text("select extname from pg_extension where extname = 'vector'")
                )
            ).scalar_one_or_none()
            column = (
                await conn.execute(
                    text(
                        "select data_type, udt_name from information_schema.columns "
                        "where table_name = 'rag_chunks' and column_name = 'embedding_vector'"
                    )
                )
            ).first()
            embedded_chunks = (
                await conn.execute(
                    text("select count(*) from rag_chunks where embedding_vector is not null")
                )
            ).scalar_one()
            print("pgvector_extension", extension)
            print("embedding_vector_column", tuple(column) if column else None)
            print("embedded_chunks", embedded_chunks)

    async with SessionLocal() as session:
        rows = await search(
            session,
            RagSearchRequest(
                project_id="aigc_rtc",
                env="dev",
                kb_ids=["aigc_voice_kb"],
                query="退款政策",
                top_k=2,
            ),
            "trace_pgvector_check",
        )
    print(
        "search_results",
        len(rows),
        rows[0]["title"] if rows else None,
        rows[0]["score"] if rows else None,
    )


def main() -> None:
    asyncio.run(check_pgvector())


if __name__ == "__main__":
    main()
