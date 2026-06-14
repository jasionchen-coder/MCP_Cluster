import hashlib
import json
import math
import time
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.rag_service.models import (
    KnowledgeBase,
    RagChunk,
    RagDocument,
    RagEvidencePack,
    RagRetrievalLog,
)
from app.modules.rag_service.schemas import DocumentCreate, KnowledgeBaseCreate, RagSearchRequest
from app.shared.config import get_settings
from app.shared.errors import APIError

CHUNK_SIZE = 120


async def create_knowledge_base(session: AsyncSession, payload: KnowledgeBaseCreate) -> KnowledgeBase:
    kb = KnowledgeBase(
        project_id=payload.project_id,
        env=payload.env,
        kb_id=payload.kb_id,
        name=payload.name,
        description=payload.description,
        collection_name=f"rag_{payload.project_id}_{payload.env}",
        permission_scope=payload.permission_scope,
        enabled=True,
    )
    session.add(kb)
    await session.commit()
    await session.refresh(kb)
    return kb


async def require_kb(
    session: AsyncSession,
    project_id: str,
    env: str,
    kb_id: str,
) -> KnowledgeBase:
    kb = (
        await session.execute(
            select(KnowledgeBase).where(KnowledgeBase.env == env, KnowledgeBase.kb_id == kb_id)
        )
    ).scalar_one_or_none()
    if kb is None:
        raise APIError(
            status_code=404,
            code="RAG_KB_NOT_FOUND",
            message="Knowledge base not found",
            details={"project_id": project_id, "env": env, "kb_id": kb_id},
        )
    if kb.project_id != project_id:
        raise APIError(
            status_code=403,
            code="RAG_ACCESS_DENIED",
            message="Knowledge base belongs to another project",
            details={"project_id": project_id, "env": env, "kb_id": kb_id},
        )
    return kb


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _chunk_text(content: str) -> list[str]:
    text = content.strip()
    return [text[i : i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)] or [""]


def _embedding_dimension() -> int:
    return get_settings().rag_embedding_dimension


def _embed_text(text_value: str) -> list[float]:
    """Create a deterministic local embedding for V1 pgvector retrieval.

    This keeps RAG usable without introducing an external embedding provider.
    The storage/search path is pgvector-ready; a model-backed embedder can
    replace this function later without changing the API contract.
    """
    dimension = _embedding_dimension()
    vector = [0.0] * dimension
    normalized = "".join(text_value.lower().split())
    if not normalized:
        return vector
    grams = [normalized[i : i + 2] for i in range(max(1, len(normalized) - 1))]
    for gram in grams:
        digest = hashlib.sha256(gram.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [round(value / norm, 6) for value in vector]


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in embedding) + "]"


def _is_postgres(session: AsyncSession) -> bool:
    bind = session.get_bind()
    return bind.dialect.name == "postgresql"


async def ingest_document(session: AsyncSession, payload: DocumentCreate) -> tuple[RagDocument, int]:
    await require_kb(session, payload.project_id, payload.env, payload.kb_id)
    doc_id = f"doc_{uuid.uuid4().hex}"
    content_hash = _hash_content(payload.content)
    document = RagDocument(
        project_id=payload.project_id,
        env=payload.env,
        kb_id=payload.kb_id,
        doc_id=doc_id,
        title=payload.title,
        source_type=payload.source_type,
        source_url=payload.source_url,
        content_hash=content_hash,
        metadata_=payload.metadata,
        status="indexed",
    )
    session.add(document)
    chunks = _chunk_text(payload.content)
    chunk_rows: list[RagChunk] = []
    for index, chunk in enumerate(chunks):
        embedding = _embed_text(f"{payload.title}\n{chunk}")
        chunk_row = RagChunk(
                project_id=payload.project_id,
                env=payload.env,
                kb_id=payload.kb_id,
                doc_id=doc_id,
                chunk_id=f"chunk_{uuid.uuid4().hex}",
                chunk_index=index,
                chunk_text=chunk,
                token_count=max(1, round(len(chunk) / 2)),
                metadata_=payload.metadata,
                embedding=embedding,
        )
        chunk_rows.append(chunk_row)
        session.add(chunk_row)
    await session.flush()
    if _is_postgres(session):
        for chunk_row in chunk_rows:
            if chunk_row.embedding:
                await session.execute(
                    text(
                        "UPDATE rag_chunks "
                        "SET embedding_vector = CAST(:embedding AS vector) "
                        "WHERE project_id = :project_id AND env = :env AND kb_id = :kb_id AND chunk_id = :chunk_id"
                    ),
                    {
                        "embedding": _vector_literal(chunk_row.embedding),
                        "project_id": chunk_row.project_id,
                        "env": chunk_row.env,
                        "kb_id": chunk_row.kb_id,
                        "chunk_id": chunk_row.chunk_id,
                    },
                )
    await session.commit()
    await session.refresh(document)
    return document, len(chunks)


async def backfill_embeddings(session: AsyncSession) -> int:
    rows = (
        await session.execute(
            select(RagChunk, RagDocument)
            .join(
                RagDocument,
                (RagDocument.project_id == RagChunk.project_id)
                & (RagDocument.env == RagChunk.env)
                & (RagDocument.kb_id == RagChunk.kb_id)
                & (RagDocument.doc_id == RagChunk.doc_id),
            )
        )
    ).all()
    updated = 0
    for chunk, document in rows:
        if not chunk.embedding:
            chunk.embedding = _embed_text(f"{document.title}\n{chunk.chunk_text}")
            updated += 1
        if _is_postgres(session) and chunk.embedding:
            await session.execute(
                text(
                    "UPDATE rag_chunks "
                    "SET embedding = CAST(:embedding_json AS jsonb), embedding_vector = CAST(:embedding AS vector) "
                    "WHERE project_id = :project_id AND env = :env AND kb_id = :kb_id AND chunk_id = :chunk_id"
                ),
                {
                    "embedding_json": json.dumps(chunk.embedding),
                    "embedding": _vector_literal(chunk.embedding),
                    "project_id": chunk.project_id,
                    "env": chunk.env,
                    "kb_id": chunk.kb_id,
                    "chunk_id": chunk.chunk_id,
                },
            )
    await session.commit()
    return updated


async def search(session: AsyncSession, payload: RagSearchRequest, trace_id: str) -> list[dict[str, Any]]:
    started = time.perf_counter()
    for kb_id in payload.kb_ids:
        await require_kb(session, payload.project_id, payload.env, kb_id)

    if get_settings().rag_vector_enabled and _is_postgres(session):
        try:
            vector_results = await _vector_search(session, payload)
            if vector_results:
                await _log_retrieval(session, payload, trace_id, started, len(vector_results), "vector")
                return vector_results
        except Exception:
            # Keep V1 resilient: pgvector can be disabled/missing while keyword
            # retrieval remains available for local development and tests.
            pass

    results = await _keyword_search(session, payload)
    await _log_retrieval(session, payload, trace_id, started, len(results), "keyword")
    return results


async def _keyword_search(session: AsyncSession, payload: RagSearchRequest) -> list[dict[str, Any]]:
    chunks = (
        await session.execute(
            select(RagChunk, RagDocument)
            .join(
                RagDocument,
                (RagDocument.project_id == RagChunk.project_id)
                & (RagDocument.env == RagChunk.env)
                & (RagDocument.kb_id == RagChunk.kb_id)
                & (RagDocument.doc_id == RagChunk.doc_id),
            )
            .where(
                RagChunk.project_id == payload.project_id,
                RagChunk.env == payload.env,
                RagChunk.kb_id.in_(payload.kb_ids),
            )
        )
    ).all()
    terms = [term for term in payload.query.split() if term]
    ranked: list[tuple[float, RagChunk, RagDocument]] = []
    for chunk, document in chunks:
        score = sum(1 for term in terms if term in chunk.chunk_text)
        if score > 0:
            ranked.append((float(score), chunk, document))
    ranked.sort(key=lambda item: (-item[0], item[1].chunk_index))
    results = [
        {
            "doc_id": doc.doc_id,
            "chunk_id": chunk.chunk_id,
            "kb_id": chunk.kb_id,
            "title": doc.title,
            "content": chunk.chunk_text,
            "score": score,
            "source_type": doc.source_type,
            "published_at": doc.metadata_.get("published_at"),
            "metadata": doc.metadata_,
        }
        for score, chunk, doc in ranked[: payload.top_k]
    ]
    return results


async def _vector_search(session: AsyncSession, payload: RagSearchRequest) -> list[dict[str, Any]]:
    query_embedding = _vector_literal(_embed_text(payload.query))
    rows = (
        await session.execute(
            text(
                """
                SELECT
                    c.doc_id,
                    c.chunk_id,
                    c.kb_id,
                    d.title,
                    c.chunk_text AS content,
                    1 - (c.embedding_vector <=> CAST(:embedding AS vector)) AS score,
                    d.source_type,
                    d.metadata AS metadata
                FROM rag_chunks c
                JOIN rag_documents d
                  ON d.project_id = c.project_id
                 AND d.env = c.env
                 AND d.kb_id = c.kb_id
                 AND d.doc_id = c.doc_id
                WHERE c.project_id = :project_id
                  AND c.env = :env
                  AND c.kb_id = ANY(:kb_ids)
                  AND c.embedding_vector IS NOT NULL
                ORDER BY c.embedding_vector <=> CAST(:embedding AS vector), c.chunk_index
                LIMIT :top_k
                """
            ),
            {
                "embedding": query_embedding,
                "project_id": payload.project_id,
                "env": payload.env,
                "kb_ids": payload.kb_ids,
                "top_k": payload.top_k,
            },
        )
    ).mappings().all()
    return [
        {
            "doc_id": row["doc_id"],
            "chunk_id": row["chunk_id"],
            "kb_id": row["kb_id"],
            "title": row["title"],
            "content": row["content"],
            "score": float(row["score"] or 0),
            "source_type": row["source_type"],
            "published_at": (row["metadata"] or {}).get("published_at"),
            "metadata": row["metadata"] or {},
        }
        for row in rows
    ]


async def _log_retrieval(
    session: AsyncSession,
    payload: RagSearchRequest,
    trace_id: str,
    started: float,
    result_count: int,
    mode: str,
) -> None:
    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    session.add(
        RagRetrievalLog(
            trace_id=trace_id,
            project_id=payload.project_id,
            env=payload.env,
            kb_ids=payload.kb_ids,
            query=payload.query,
            top_k=payload.top_k,
            result_count=result_count,
            latency_ms=latency_ms,
            status="success",
            error_message=f"mode={mode}",
        )
    )
    await session.commit()


async def create_evidence_pack(
    session: AsyncSession,
    payload: RagSearchRequest,
    trace_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    results = await search(session, payload, trace_id)
    items = [
        {
            "doc_id": item["doc_id"],
            "chunk_id": item["chunk_id"],
            "title": item["title"],
            "source": item["metadata"].get("source"),
            "published_at": item["published_at"],
            "content": item["content"],
            "summary": item["content"][:80],
            "score": item["score"],
        }
        for item in results
    ]
    evidence_pack_id = f"evp_{uuid.uuid4().hex}"
    session.add(
        RagEvidencePack(
            evidence_pack_id=evidence_pack_id,
            trace_id=trace_id,
            project_id=payload.project_id,
            env=payload.env,
            query=payload.query,
            items=items,
        )
    )
    await session.commit()
    return evidence_pack_id, items
