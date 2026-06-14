from typing import Any

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    project_id: str
    env: str
    kb_id: str
    name: str
    description: str | None = None
    permission_scope: str = "private"


class KnowledgeBaseResponse(KnowledgeBaseCreate):
    collection_name: str
    enabled: bool


class DocumentCreate(BaseModel):
    project_id: str
    env: str
    kb_id: str
    source_type: str
    title: str
    content: str
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    doc_id: str
    status: str
    chunk_count: int
    content_hash: str


class RagSearchRequest(BaseModel):
    project_id: str
    env: str
    kb_ids: list[str]
    query: str
    top_k: int = 8
    filters: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


class RagSearchResult(BaseModel):
    doc_id: str
    chunk_id: str
    kb_id: str
    title: str
    content: str
    score: float
    source_type: str
    published_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagSearchResponse(BaseModel):
    query: str
    results: list[RagSearchResult]
    trace_id: str


class EvidencePackResponse(BaseModel):
    evidence_pack_id: str
    project_id: str
    env: str
    query: str
    items: list[dict[str, Any]]
    trace_id: str
