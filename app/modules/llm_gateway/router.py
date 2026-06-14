import json
import time
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm_gateway.schemas import (
    ChatCompletionsRequest,
    ImageGenerateRequest,
    ImageGenerateResponse,
    ImageResultSchema,
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMJsonGenerateRequest,
    LLMJsonGenerateResponse,
    LLMUsage,
)
from app.modules.llm_gateway.service import generate, parse_json_content
from app.modules.llm_gateway.service import image_generate
from app.modules.llm_gateway.service import stream_generate
from app.shared.database import get_session
from app.shared.tracing import get_trace_id

router = APIRouter(tags=["llm-gateway"])


@router.post("/api/v1/llm/generate", response_model=LLMGenerateResponse)
async def generate_endpoint(
    payload: LLMGenerateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> LLMGenerateResponse:
    trace_id = payload.trace_id or get_trace_id(request)
    request_id, result, latency_ms = await generate(session, payload, trace_id)
    return LLMGenerateResponse(
        request_id=request_id,
        project_id=payload.project_id,
        task_type=payload.task_type,
        model=result.model,
        content=result.content,
        usage=LLMUsage(**result.usage),
        latency_ms=latency_ms,
        finish_reason=result.finish_reason,
        tool_calls=result.tool_calls,
        trace_id=trace_id,
    )


@router.post("/api/v1/llm/stream")
async def stream_generate_endpoint(
    payload: LLMGenerateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    trace_id = payload.trace_id or get_trace_id(request)

    async def event_stream() -> AsyncIterator[str]:
        async for chunk in stream_generate(session, payload, trace_id):
            yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/api/v1/llm/json-generate", response_model=LLMJsonGenerateResponse)
async def json_generate_endpoint(
    payload: LLMJsonGenerateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> LLMJsonGenerateResponse:
    trace_id = payload.trace_id or get_trace_id(request)
    request_id, result, latency_ms = await generate(session, payload, trace_id)
    json_content = parse_json_content(result.content, payload.json_schema)
    return LLMJsonGenerateResponse(
        request_id=request_id,
        project_id=payload.project_id,
        task_type=payload.task_type,
        model=result.model,
        content=result.content,
        json_content=json_content,
        usage=LLMUsage(**result.usage),
        latency_ms=latency_ms,
        finish_reason=result.finish_reason,
        trace_id=trace_id,
    )


@router.post("/v1/chat/completions")
async def chat_completions_endpoint(
    payload: ChatCompletionsRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    request_payload = LLMGenerateRequest(
        project_id=payload.project_id,
        env=payload.env,
        task_type=payload.task_type,
        model_policy_id=payload.model,
        messages=payload.messages,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )
    trace_id = get_trace_id(request)
    request_id, result, _latency_ms = await generate(session, request_payload, trace_id)
    return {
        "id": request_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": result.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.content},
                "finish_reason": result.finish_reason,
            }
        ],
        "usage": result.usage,
    }


@router.post("/api/v1/llm/image-generate", response_model=ImageGenerateResponse)
async def image_generate_endpoint(
    payload: ImageGenerateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ImageGenerateResponse:
    trace_id = payload.trace_id or get_trace_id(request)
    request_id, urls, model, latency_ms = await image_generate(
        session, payload, trace_id
    )
    return ImageGenerateResponse(
        request_id=request_id,
        project_id=payload.project_id,
        task_type=payload.task_type,
        model=model,
        images=[ImageResultSchema(url=u) for u in urls],
        latency_ms=latency_ms,
        trace_id=trace_id,
    )
