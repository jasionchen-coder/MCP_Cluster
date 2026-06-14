from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.rag_service.schemas import (
    DocumentCreate,
    DocumentResponse,
    EvidencePackResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    RagSearchRequest,
    RagSearchResponse,
)
from app.modules.rag_service.service import (
    create_evidence_pack,
    create_knowledge_base,
    ingest_document,
    search,
)
from app.shared.database import get_session
from app.shared.tracing import get_trace_id

router = APIRouter(prefix="/api/v1/rag", tags=["rag-service"])


@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse)
async def create_kb_endpoint(
    payload: KnowledgeBaseCreate,
    session: AsyncSession = Depends(get_session),
) -> KnowledgeBaseResponse:
    kb = await create_knowledge_base(session, payload)
    return KnowledgeBaseResponse(
        project_id=kb.project_id,
        env=kb.env,
        kb_id=kb.kb_id,
        name=kb.name,
        description=kb.description,
        permission_scope=kb.permission_scope,
        collection_name=kb.collection_name,
        enabled=kb.enabled,
    )


@router.post("/documents", response_model=DocumentResponse)
async def ingest_document_endpoint(
    payload: DocumentCreate,
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    doc, chunk_count = await ingest_document(session, payload)
    return DocumentResponse(
        doc_id=doc.doc_id,
        status=doc.status,
        chunk_count=chunk_count,
        content_hash=doc.content_hash,
    )


@router.post("/search", response_model=RagSearchResponse)
async def search_endpoint(
    payload: RagSearchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RagSearchResponse:
    trace_id = payload.trace_id or get_trace_id(request)
    results = await search(session, payload, trace_id)
    return RagSearchResponse(query=payload.query, results=results, trace_id=trace_id)


@router.post("/evidence-pack", response_model=EvidencePackResponse)
async def evidence_pack_endpoint(
    payload: RagSearchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> EvidencePackResponse:
    trace_id = payload.trace_id or get_trace_id(request)
    evidence_pack_id, items = await create_evidence_pack(session, payload, trace_id)
    return EvidencePackResponse(
        evidence_pack_id=evidence_pack_id,
        project_id=payload.project_id,
        env=payload.env,
        query=payload.query,
        items=items,
        trace_id=trace_id,
    )
