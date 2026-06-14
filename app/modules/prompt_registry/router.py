from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.prompt_registry.schemas import (
    PromptCreate,
    PromptRenderRequest,
    PromptRenderResponse,
    PromptResponse,
    PromptVersionCreate,
    PromptVersionResponse,
)
from app.modules.prompt_registry.service import (
    create_prompt,
    create_prompt_version,
    publish_prompt_version,
    render_prompt,
)
from app.shared.database import get_session
from app.shared.tracing import get_trace_id

router = APIRouter(prefix="/api/v1/prompts", tags=["prompt-registry"])


@router.post("", response_model=PromptResponse)
async def create_prompt_endpoint(
    payload: PromptCreate,
    session: AsyncSession = Depends(get_session),
) -> PromptResponse:
    prompt = await create_prompt(session, payload)
    return PromptResponse(
        project_id=prompt.project_id,
        prompt_key=prompt.prompt_key,
        name=prompt.name,
        description=prompt.description,
        default_version=prompt.default_version,
        enabled=prompt.enabled,
    )


@router.post("/{prompt_key}/versions", response_model=PromptVersionResponse)
async def create_version_endpoint(
    prompt_key: str,
    payload: PromptVersionCreate,
    session: AsyncSession = Depends(get_session),
) -> PromptVersionResponse:
    version = await create_prompt_version(session, prompt_key, payload)
    return PromptVersionResponse(
        prompt_key=version.prompt_key,
        version=version.version,
        content=version.content,
        variables_schema=version.variables_schema,
        status=version.status,
    )


@router.post("/{prompt_key}/versions/{version}/publish", response_model=PromptVersionResponse)
async def publish_version_endpoint(
    prompt_key: str,
    version: str,
    session: AsyncSession = Depends(get_session),
) -> PromptVersionResponse:
    prompt_version = await publish_prompt_version(session, prompt_key, version)
    return PromptVersionResponse(
        prompt_key=prompt_version.prompt_key,
        version=prompt_version.version,
        content=prompt_version.content,
        variables_schema=prompt_version.variables_schema,
        status=prompt_version.status,
    )


@router.post("/render", response_model=PromptRenderResponse)
async def render_prompt_endpoint(
    payload: PromptRenderRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> PromptRenderResponse:
    trace_id = payload.trace_id or get_trace_id(request)
    version, rendered, variables_used = await render_prompt(
        session=session,
        project_id=payload.project_id,
        env=payload.env,
        prompt_key=payload.prompt_key,
        version=payload.version,
        variables=payload.variables,
        trace_id=trace_id,
    )
    return PromptRenderResponse(
        prompt_key=payload.prompt_key,
        version=version,
        rendered_content=rendered,
        variables_used=variables_used,
        trace_id=trace_id,
    )
