import asyncio
import os
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.modules.config_center.schemas import TaskConfigUpsert
from app.modules.config_center.service import (
    get_task_config,
    list_change_logs,
    upsert_task_config,
)
from app.modules.llm_gateway.schemas import (
    ImageGenerateRequest,
    LLMGenerateRequest,
    LLMJsonGenerateRequest,
)
from app.modules.llm_gateway.service import generate, image_generate, parse_json_content
from app.modules.prompt_registry.schemas import (
    PromptCreate,
    PromptVersionCreate,
)
from app.modules.prompt_registry.service import (
    create_prompt,
    create_prompt_version,
    publish_prompt_version,
    render_prompt,
)
from app.modules.rag_service.schemas import (
    DocumentCreate,
    KnowledgeBaseCreate,
    RagSearchRequest,
)
from app.modules.rag_service.service import (
    create_evidence_pack,
    create_knowledge_base,
    ingest_document,
    search,
)
from app.modules.secret_manager.schemas import SecretUpsert
from app.modules.secret_manager.service import (
    get_secret_metadata,
    list_secrets,
    resolve_secret_value,
    secret_ref,
    upsert_secret,
)
from app.modules.tool_registry.schemas import ToolUpsert
from app.modules.tool_registry.service import (
    get_tool,
    list_tools,
    upsert_tool,
)
from app.shared.database import SessionLocal, init_db

mcp = FastMCP(
    "mcp-shared-services",
    host=os.getenv("MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("MCP_PORT", "8401")),
    sse_path=os.getenv("MCP_SSE_PATH", "/sse"),
    message_path=os.getenv("MCP_MESSAGE_PATH", "/messages/"),
    streamable_http_path=os.getenv("MCP_STREAMABLE_HTTP_PATH", "/mcp"),
)

_init_lock = asyncio.Lock()
_initialized = False


async def _ensure_initialized() -> None:
    global _initialized
    if _initialized:
        return
    async with _init_lock:
        if not _initialized:
            await init_db()
            _initialized = True


def _trace_id(trace_id: str | None) -> str:
    return trace_id or f"trace_{uuid.uuid4().hex}"


@mcp.tool()
async def secret_upsert(
    project_id: str,
    env: str,
    secret_key: str,
    secret_value: str,
    description: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """Create or update an encrypted secret and return metadata only."""
    await _ensure_initialized()
    payload = SecretUpsert(secret_value=secret_value, description=description, enabled=enabled)
    async with SessionLocal() as session:
        secret = await upsert_secret(session, project_id, env, secret_key, payload)
        return secret.metadata_dict()


@mcp.tool()
async def secret_get_metadata(project_id: str, env: str, secret_key: str) -> dict[str, Any]:
    """Read secret metadata without revealing the plaintext value."""
    await _ensure_initialized()
    async with SessionLocal() as session:
        secret = await get_secret_metadata(session, project_id, env, secret_key)
        return secret.metadata_dict()


@mcp.tool()
async def secret_list(
    project_id: str | None = None,
    env: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """List secret metadata without revealing plaintext values."""
    await _ensure_initialized()
    async with SessionLocal() as session:
        secrets = await list_secrets(session, project_id=project_id, env=env, enabled=enabled)
        return {"items": [secret.metadata_dict() for secret in secrets]}


@mcp.tool()
async def secret_resolve(project_id: str, env: str, secret_key: str) -> dict[str, Any]:
    """Resolve an enabled secret value for trusted service-side use."""
    await _ensure_initialized()
    async with SessionLocal() as session:
        secret, secret_value = await resolve_secret_value(session, project_id, env, secret_key)
        return {
            "project_id": project_id,
            "env": env,
            "secret_key": secret_key,
            "secret_ref": secret_ref(project_id, env, secret_key),
            "secret_value": secret_value,
            "version": secret.version,
        }


@mcp.tool()
async def tool_registry_upsert(
    project_id: str,
    env: str,
    tool_id: str,
    display_name: str,
    tool_type: str,
    description: str | None = None,
    endpoint_config: dict[str, Any] | None = None,
    input_schema: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
    auth_type: str = "none",
    secret_ref: str | None = None,
    permission_scope: str = "project",
    tags: list[str] | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """Create or update a tool definition in Tool Registry."""
    await _ensure_initialized()
    payload = ToolUpsert(
        display_name=display_name,
        description=description,
        tool_type=tool_type,  # type: ignore[arg-type]
        endpoint_config=endpoint_config or {},
        input_schema=input_schema or {},
        output_schema=output_schema or {},
        auth_type=auth_type,  # type: ignore[arg-type]
        secret_ref=secret_ref,
        permission_scope=permission_scope,  # type: ignore[arg-type]
        tags=tags or [],
        enabled=enabled,
    )
    async with SessionLocal() as session:
        tool = await upsert_tool(session, project_id, env, tool_id, payload)
        return tool.as_dict()


@mcp.tool()
async def tool_registry_get(project_id: str, env: str, tool_id: str) -> dict[str, Any]:
    """Read one registered tool definition."""
    await _ensure_initialized()
    async with SessionLocal() as session:
        tool = await get_tool(session, project_id, env, tool_id)
        return tool.as_dict()


@mcp.tool()
async def tool_registry_list(
    project_id: str | None = None,
    env: str | None = None,
    tool_type: str | None = None,
    enabled: bool | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """List registered tool definitions for agent planning and governance."""
    await _ensure_initialized()
    async with SessionLocal() as session:
        tools = await list_tools(
            session,
            project_id=project_id,
            env=env,
            tool_type=tool_type,
            enabled=enabled,
            tag=tag,
        )
        return {"items": [tool.as_dict() for tool in tools]}


@mcp.tool()
async def config_get_task(project_id: str, env: str, task_type: str) -> dict[str, Any]:
    """读取 Config Center 中某个项目、环境、任务的共享配置。"""
    await _ensure_initialized()
    async with SessionLocal() as session:
        config = await get_task_config(session, project_id, env, task_type)
        return config.as_dict()


@mcp.tool()
async def config_upsert_task(
    project_id: str,
    env: str,
    task_type: str,
    prompt_key: str,
    prompt_version: str,
    model_policy_id: str,
    rag_enabled: bool = False,
    rag_policy_id: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """新增或更新 Config Center 的任务配置。"""
    await _ensure_initialized()
    payload = TaskConfigUpsert(
        prompt_key=prompt_key,
        prompt_version=prompt_version,
        model_policy_id=model_policy_id,
        rag_enabled=rag_enabled,
        rag_policy_id=rag_policy_id,
        enabled=enabled,
    )
    async with SessionLocal() as session:
        config = await upsert_task_config(session, project_id, env, task_type, payload)
        return config.as_dict()


@mcp.tool()
async def config_list_change_logs(
    project_id: str | None = None,
    env: str | None = None,
) -> dict[str, Any]:
    """查询 Config Center 配置变更日志。"""
    await _ensure_initialized()
    async with SessionLocal() as session:
        logs = await list_change_logs(session, project_id=project_id, env=env)
        return {
            "items": [
                {
                    "id": log.id,
                    "project_id": log.project_id,
                    "env": log.env,
                    "config_type": log.config_type,
                    "config_key": log.config_key,
                    "before_value": log.before_value,
                    "after_value": log.after_value,
                    "changed_by": log.changed_by,
                }
                for log in logs
            ]
        }


@mcp.tool()
async def prompt_create(
    project_id: str,
    prompt_key: str,
    name: str,
    default_version: str,
    description: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """在 Prompt Registry 中创建 Prompt 模板元数据。"""
    await _ensure_initialized()
    payload = PromptCreate(
        project_id=project_id,
        prompt_key=prompt_key,
        name=name,
        description=description,
        default_version=default_version,
        enabled=enabled,
    )
    async with SessionLocal() as session:
        prompt = await create_prompt(session, payload)
        return {
            "project_id": prompt.project_id,
            "prompt_key": prompt.prompt_key,
            "name": prompt.name,
            "description": prompt.description,
            "default_version": prompt.default_version,
            "enabled": prompt.enabled,
        }


@mcp.tool()
async def prompt_create_version(
    prompt_key: str,
    version: str,
    content: str,
    variables_schema: dict[str, Any] | None = None,
    status: str = "draft",
) -> dict[str, Any]:
    """为已有 Prompt 新增一个版本。"""
    await _ensure_initialized()
    payload = PromptVersionCreate(
        version=version,
        content=content,
        variables_schema=variables_schema or {},
        status=status,
    )
    async with SessionLocal() as session:
        prompt_version = await create_prompt_version(session, prompt_key, payload)
        return {
            "prompt_key": prompt_version.prompt_key,
            "version": prompt_version.version,
            "content": prompt_version.content,
            "variables_schema": prompt_version.variables_schema,
            "status": prompt_version.status,
        }


@mcp.tool()
async def prompt_publish_version(prompt_key: str, version: str) -> dict[str, Any]:
    """发布指定 Prompt 版本。"""
    await _ensure_initialized()
    async with SessionLocal() as session:
        prompt_version = await publish_prompt_version(session, prompt_key, version)
        return {
            "prompt_key": prompt_version.prompt_key,
            "version": prompt_version.version,
            "content": prompt_version.content,
            "variables_schema": prompt_version.variables_schema,
            "status": prompt_version.status,
        }


@mcp.tool()
async def prompt_render(
    project_id: str,
    env: str,
    prompt_key: str,
    variables: dict[str, Any] | None = None,
    version: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """渲染 Prompt Registry 中的模板，返回最终提示词文本。"""
    await _ensure_initialized()
    effective_trace_id = _trace_id(trace_id)
    async with SessionLocal() as session:
        effective_version, rendered, variables_used = await render_prompt(
            session=session,
            project_id=project_id,
            env=env,
            prompt_key=prompt_key,
            version=version,
            variables=variables or {},
            trace_id=effective_trace_id,
        )
        return {
            "prompt_key": prompt_key,
            "version": effective_version,
            "rendered_content": rendered,
            "variables_used": variables_used,
            "trace_id": effective_trace_id,
        }


@mcp.tool()
async def rag_create_knowledge_base(
    project_id: str,
    env: str,
    kb_id: str,
    name: str,
    description: str | None = None,
    permission_scope: str = "private",
) -> dict[str, Any]:
    """创建 RAG Service 知识库。"""
    await _ensure_initialized()
    payload = KnowledgeBaseCreate(
        project_id=project_id,
        env=env,
        kb_id=kb_id,
        name=name,
        description=description,
        permission_scope=permission_scope,
    )
    async with SessionLocal() as session:
        kb = await create_knowledge_base(session, payload)
        return {
            "project_id": kb.project_id,
            "env": kb.env,
            "kb_id": kb.kb_id,
            "name": kb.name,
            "description": kb.description,
            "permission_scope": kb.permission_scope,
            "collection_name": kb.collection_name,
            "enabled": kb.enabled,
        }


@mcp.tool()
async def rag_ingest_document(
    project_id: str,
    env: str,
    kb_id: str,
    source_type: str,
    title: str,
    content: str,
    source_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """向 RAG Service 知识库写入文档并切块索引。"""
    await _ensure_initialized()
    payload = DocumentCreate(
        project_id=project_id,
        env=env,
        kb_id=kb_id,
        source_type=source_type,
        title=title,
        content=content,
        source_url=source_url,
        metadata=metadata or {},
    )
    async with SessionLocal() as session:
        document, chunk_count = await ingest_document(session, payload)
        return {
            "doc_id": document.doc_id,
            "status": document.status,
            "chunk_count": chunk_count,
            "content_hash": document.content_hash,
        }


@mcp.tool()
async def rag_search(
    project_id: str,
    env: str,
    kb_ids: list[str],
    query: str,
    top_k: int = 8,
    filters: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """调用 RAG Service 检索知识库，PostgreSQL 下会优先使用 pgvector。"""
    await _ensure_initialized()
    effective_trace_id = _trace_id(trace_id)
    payload = RagSearchRequest(
        project_id=project_id,
        env=env,
        kb_ids=kb_ids,
        query=query,
        top_k=top_k,
        filters=filters or {},
        trace_id=effective_trace_id,
    )
    async with SessionLocal() as session:
        results = await search(session, payload, effective_trace_id)
        return {
            "query": query,
            "results": [result.model_dump() for result in results],
            "trace_id": effective_trace_id,
        }


@mcp.tool()
async def rag_create_evidence_pack(
    project_id: str,
    env: str,
    kb_ids: list[str],
    query: str,
    top_k: int = 8,
    filters: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """基于 RAG 检索结果生成证据包，适合文章生成或客服回答前置取材。"""
    await _ensure_initialized()
    effective_trace_id = _trace_id(trace_id)
    payload = RagSearchRequest(
        project_id=project_id,
        env=env,
        kb_ids=kb_ids,
        query=query,
        top_k=top_k,
        filters=filters or {},
        trace_id=effective_trace_id,
    )
    async with SessionLocal() as session:
        evidence_pack_id, items = await create_evidence_pack(session, payload, effective_trace_id)
        return {
            "evidence_pack_id": evidence_pack_id,
            "project_id": project_id,
            "env": env,
            "query": query,
            "items": items,
            "trace_id": effective_trace_id,
        }


@mcp.tool()
async def llm_generate(
    project_id: str,
    env: str,
    task_type: str,
    model_policy_id: str,
    messages: list[dict[str, Any]],
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """调用 LLM Gateway 生成普通文本。"""
    await _ensure_initialized()
    effective_trace_id = _trace_id(trace_id)
    payload = LLMGenerateRequest(
        project_id=project_id,
        env=env,
        task_type=task_type,
        model_policy_id=model_policy_id,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        tool_choice=tool_choice,
        trace_id=effective_trace_id,
    )
    async with SessionLocal() as session:
        request_id, result, latency_ms = await generate(session, payload, effective_trace_id)
        return {
            "request_id": request_id,
            "project_id": project_id,
            "task_type": task_type,
            "model": result.model,
            "content": result.content,
            "usage": result.usage,
            "latency_ms": latency_ms,
            "finish_reason": result.finish_reason,
            "tool_calls": result.tool_calls,
            "trace_id": effective_trace_id,
        }


@mcp.tool()
async def llm_json_generate(
    project_id: str,
    env: str,
    task_type: str,
    model_policy_id: str,
    messages: list[dict[str, Any]],
    json_schema: dict[str, Any] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """调用 LLM Gateway 生成 JSON，并按 required 字段做基础校验。"""
    await _ensure_initialized()
    effective_trace_id = _trace_id(trace_id)
    schema = json_schema or {}
    payload = LLMJsonGenerateRequest(
        project_id=project_id,
        env=env,
        task_type=task_type,
        model_policy_id=model_policy_id,
        messages=messages,
        json_schema=schema,
        temperature=temperature,
        max_tokens=max_tokens,
        trace_id=effective_trace_id,
    )
    async with SessionLocal() as session:
        request_id, result, latency_ms = await generate(session, payload, effective_trace_id)
        return {
            "request_id": request_id,
            "project_id": project_id,
            "task_type": task_type,
            "model": result.model,
            "content": result.content,
            "json_content": parse_json_content(result.content, schema),
            "usage": result.usage,
            "latency_ms": latency_ms,
            "finish_reason": result.finish_reason,
            "trace_id": effective_trace_id,
        }


@mcp.tool()
async def llm_image_generate(
    project_id: str,
    env: str,
    task_type: str,
    model_policy_id: str,
    prompts: list[str],
    size: str = "2K",
    trace_id: str | None = None,
) -> dict[str, Any]:
    """调用 LLM Gateway 图片生成模型，返回图片 URL 列表。"""
    await _ensure_initialized()
    effective_trace_id = _trace_id(trace_id)
    payload = ImageGenerateRequest(
        project_id=project_id,
        env=env,
        task_type=task_type,
        model_policy_id=model_policy_id,
        prompts=prompts,
        size=size,
        trace_id=effective_trace_id,
    )
    async with SessionLocal() as session:
        request_id, urls, model, latency_ms = await image_generate(session, payload, effective_trace_id)
        return {
            "request_id": request_id,
            "project_id": project_id,
            "task_type": task_type,
            "model": model,
            "images": [{"url": url} for url in urls],
            "latency_ms": latency_ms,
            "trace_id": effective_trace_id,
        }


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError("MCP_TRANSPORT must be one of: stdio, sse, streamable-http")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
