import asyncio
import json
import time
import uuid
from typing import Any, AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm_gateway.models import (
    LLMInvocationLog,
    LLMModelEndpoint,
    LLMModelPolicy,
    LLMModelProvider,
)
from app.modules.llm_gateway.provider import ProviderResult, get_provider
from app.modules.llm_gateway.schemas import ImageGenerateRequest, LLMGenerateRequest
from app.shared.errors import APIError


async def get_policy(
    session: AsyncSession,
    project_id: str,
    env: str,
    task_type: str,
    model_policy_id: str,
) -> tuple[LLMModelPolicy, LLMModelEndpoint, LLMModelProvider]:
    policy = (
        await session.execute(
            select(LLMModelPolicy).where(
                LLMModelPolicy.project_id == project_id,
                LLMModelPolicy.env == env,
                LLMModelPolicy.task_type == task_type,
                LLMModelPolicy.policy_id == model_policy_id,
                LLMModelPolicy.enabled.is_(True),
            )
        )
    ).scalar_one_or_none()
    if policy is None:
        raise APIError(
            status_code=404,
            code="MODEL_POLICY_NOT_FOUND",
            message="Model policy not found",
            details={
                "project_id": project_id,
                "env": env,
                "task_type": task_type,
                "model_policy_id": model_policy_id,
            },
        )
    endpoint = await session.get(LLMModelEndpoint, policy.primary_model_id)
    if endpoint is None or not endpoint.enabled:
        raise APIError(
            status_code=404,
            code="MODEL_POLICY_NOT_FOUND",
            message="Primary model endpoint not found",
            details={"model_policy_id": model_policy_id},
        )
    provider = await session.get(LLMModelProvider, endpoint.provider_id)
    if provider is None or not provider.enabled:
        raise APIError(
            status_code=404,
            code="MODEL_POLICY_NOT_FOUND",
            message="Model provider not found",
            details={"model_policy_id": model_policy_id},
        )
    return policy, endpoint, provider


async def generate(
    session: AsyncSession,
    payload: LLMGenerateRequest,
    trace_id: str,
) -> tuple[str, ProviderResult, int]:
    policy, endpoint, provider_model = await get_policy(
        session,
        payload.project_id,
        payload.env,
        payload.task_type,
        payload.model_policy_id,
    )
    provider = get_provider(provider_model.base_url, provider_model.api_key_env)
    temperature = payload.temperature if payload.temperature is not None else policy.default_temperature
    max_tokens = payload.max_tokens if payload.max_tokens is not None else policy.default_max_tokens
    request_id = f"llm_req_{uuid.uuid4().hex}"
    started = time.perf_counter()
    try:
        result = await provider.generate(
            model=endpoint.endpoint_id,
            messages=payload.messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=payload.tools,
            tool_choice=payload.tool_choice,
        )
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        await log_invocation(
            session=session,
            request_id=request_id,
            trace_id=trace_id,
            payload=payload,
            provider_name=provider_model.provider_name,
            model_name=result.model,
            usage=result.usage,
            latency_ms=latency_ms,
            status="success",
            error_message=None,
        )
        return request_id, result, latency_ms
    except Exception as exc:
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        await log_invocation(
            session=session,
            request_id=request_id,
            trace_id=trace_id,
            payload=payload,
            provider_name=provider_model.provider_name,
            model_name=endpoint.endpoint_id,
            usage={},
            latency_ms=latency_ms,
            status="error",
            error_message=f"{type(exc).__name__}: {exc}",
        )
        raise


async def stream_generate(
    session: AsyncSession,
    payload: LLMGenerateRequest,
    trace_id: str,
) -> AsyncIterator[str]:
    policy, endpoint, provider_model = await get_policy(
        session,
        payload.project_id,
        payload.env,
        payload.task_type,
        payload.model_policy_id,
    )
    provider = get_provider(provider_model.base_url, provider_model.api_key_env)
    temperature = payload.temperature if payload.temperature is not None else policy.default_temperature
    max_tokens = payload.max_tokens if payload.max_tokens is not None else policy.default_max_tokens
    request_id = f"stream_req_{uuid.uuid4().hex}"
    started = time.perf_counter()
    full_text = ""
    try:
        async for chunk in provider.stream_generate(
            model=endpoint.endpoint_id,
            messages=payload.messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            full_text += chunk
            yield chunk
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        await log_invocation(
            session=session,
            request_id=request_id,
            trace_id=trace_id,
            payload=payload,
            provider_name=provider_model.provider_name,
            model_name=endpoint.endpoint_id,
            usage={},
            latency_ms=latency_ms,
            status="success",
            error_message=None,
        )
    except Exception as exc:
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        await log_invocation(
            session=session,
            request_id=request_id,
            trace_id=trace_id,
            payload=payload,
            provider_name=provider_model.provider_name,
            model_name=endpoint.endpoint_id,
            usage={},
            latency_ms=latency_ms,
            status="error",
            error_message=f"{type(exc).__name__}: {exc}",
        )
        raise


async def log_invocation(
    *,
    session: AsyncSession,
    request_id: str,
    trace_id: str,
    payload: LLMGenerateRequest,
    provider_name: str,
    model_name: str,
    usage: dict[str, int],
    latency_ms: int,
    status: str,
    error_message: str | None,
) -> None:
    session.add(
        LLMInvocationLog(
            request_id=request_id,
            trace_id=trace_id,
            project_id=payload.project_id,
            env=payload.env,
            task_type=payload.task_type,
            model_policy_id=payload.model_policy_id,
            provider_name=provider_name,
            model_name=model_name,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
        )
    )
    await session.commit()


def parse_json_content(content: str, schema: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise APIError(
            status_code=400,
            code="INVALID_JSON_OUTPUT",
            message="Model output is not valid JSON",
            details={"error": str(exc)},
        ) from exc
    if not isinstance(parsed, dict):
        raise APIError(
            status_code=400,
            code="INVALID_JSON_OUTPUT",
            message="Model output must be a JSON object",
            details={},
        )
    missing = [name for name in schema.get("required", []) if name not in parsed]
    if missing:
        raise APIError(
            status_code=400,
            code="INVALID_JSON_OUTPUT",
            message="Model output misses required JSON fields",
            details={"missing": missing},
        )
    return parsed


async def image_generate(
    session: AsyncSession,
    payload: ImageGenerateRequest,
    trace_id: str,
) -> tuple[str, list[str], str, int]:
    policy, endpoint, provider_model = await get_policy(
        session,
        payload.project_id,
        payload.env,
        payload.task_type,
        payload.model_policy_id,
    )
    provider = get_provider(provider_model.base_url, provider_model.api_key_env)
    request_id = f"img_req_{uuid.uuid4().hex}"
    started = time.perf_counter()
    try:
        results = []
        tasks = [
            provider.image_generate(
                model=endpoint.endpoint_id,
                prompt=prompt,
                size=payload.size,
            )
            for prompt in payload.prompts
        ]
        image_results = await asyncio.gather(*tasks)
        results = [r.url for r in image_results]
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        await log_invocation(
            session=session,
            request_id=request_id,
            trace_id=trace_id,
            payload=LLMGenerateRequest(
                project_id=payload.project_id,
                env=payload.env,
                task_type=payload.task_type,
                model_policy_id=payload.model_policy_id,
                messages=[{"role": "user", "content": p} for p in payload.prompts],
            ),
            provider_name=provider_model.provider_name,
            model_name=endpoint.endpoint_id,
            usage={},
            latency_ms=latency_ms,
            status="success",
            error_message=None,
        )
        return request_id, results, endpoint.endpoint_id, latency_ms
    except Exception as exc:
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        await log_invocation(
            session=session,
            request_id=request_id,
            trace_id=trace_id,
            payload=LLMGenerateRequest(
                project_id=payload.project_id,
                env=payload.env,
                task_type=payload.task_type,
                model_policy_id=payload.model_policy_id,
                messages=[{"role": "user", "content": p} for p in payload.prompts],
            ),
            provider_name=provider_model.provider_name,
            model_name=endpoint.endpoint_id,
            usage={},
            latency_ms=latency_ms,
            status="error",
            error_message=f"{type(exc).__name__}: {exc}",
        )
        raise
