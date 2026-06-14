import hashlib
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.rag_service.models import (
    KnowledgeBase,
    RagChunk,
    RagDocument,
    RagEvidencePack,
    RagRetrievalLog,
)
from app.modules.rag_service.schemas import DocumentCreate, KnowledgeBaseCreate, RagSearchRequest
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
    for index, chunk in enumerate(chunks):
        session.add(
            RagChunk(
                project_id=payload.project_id,
                env=payload.env,
                kb_id=payload.kb_id,
                doc_id=doc_id,
                chunk_id=f"chunk_{uuid.uuid4().hex}",
                chunk_index=index,
                chunk_text=chunk,
                token_count=max(1, round(len(chunk) / 2)),
                metadata_=payload.metadata,
            )
        )
    await session.commit()
    await session.refresh(document)
    return document, len(chunks)


async def search(session: AsyncSession, payload: RagSearchRequest, trace_id: str) -> list[dict[str, Any]]:
    started = time.perf_counter()
    for kb_id in payload.kb_ids:
        await require_kb(session, payload.project_id, payload.env, kb_id)
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
    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    session.add(
        RagRetrievalLog(
            trace_id=trace_id,
            project_id=payload.project_id,
            env=payload.env,
            kb_ids=payload.kb_ids,
            query=payload.query,
            top_k=payload.top_k,
            result_count=len(results),
            latency_ms=latency_ms,
            status="success",
            error_message=None,
        )
    )
    await session.commit()
    return results


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
