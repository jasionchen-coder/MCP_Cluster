import hashlib
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.prompt_registry.models import (
    PromptRenderLog,
    PromptTemplate,
    PromptVersion,
)
from app.modules.prompt_registry.schemas import PromptCreate, PromptVersionCreate
from app.shared.errors import APIError

VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


async def create_prompt(session: AsyncSession, payload: PromptCreate) -> PromptTemplate:
    prompt = PromptTemplate(**payload.model_dump())
    session.add(prompt)
    await session.commit()
    await session.refresh(prompt)
    return prompt


async def create_prompt_version(
    session: AsyncSession,
    prompt_key: str,
    payload: PromptVersionCreate,
) -> PromptVersion:
    await get_prompt(session, prompt_key)
    version = PromptVersion(prompt_key=prompt_key, **payload.model_dump())
    session.add(version)
    await session.commit()
    await session.refresh(version)
    return version


async def publish_prompt_version(
    session: AsyncSession,
    prompt_key: str,
    version: str,
) -> PromptVersion:
    prompt_version = await get_prompt_version(session, prompt_key, version)
    prompt_version.status = "published"
    await session.commit()
    await session.refresh(prompt_version)
    return prompt_version


async def get_prompt(session: AsyncSession, prompt_key: str) -> PromptTemplate:
    prompt = (
        await session.execute(select(PromptTemplate).where(PromptTemplate.prompt_key == prompt_key))
    ).scalar_one_or_none()
    if prompt is None:
        raise APIError(
            status_code=404,
            code="PROMPT_NOT_FOUND",
            message="Prompt not found",
            details={"prompt_key": prompt_key},
        )
    return prompt


async def get_prompt_version(session: AsyncSession, prompt_key: str, version: str) -> PromptVersion:
    prompt_version = (
        await session.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_key == prompt_key,
                PromptVersion.version == version,
            )
        )
    ).scalar_one_or_none()
    if prompt_version is None:
        raise APIError(
            status_code=404,
            code="PROMPT_NOT_FOUND",
            message="Prompt version not found",
            details={"prompt_key": prompt_key, "version": version},
        )
    return prompt_version


def _variables_hash(variables: dict[str, Any]) -> str:
    raw = json.dumps(variables, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _required_variables(schema: dict[str, Any]) -> list[str]:
    required = schema.get("required", [])
    return [str(item) for item in required]


async def render_prompt(
    session: AsyncSession,
    project_id: str,
    env: str,
    prompt_key: str,
    version: str | None,
    variables: dict[str, Any],
    trace_id: str,
) -> tuple[str, str, list[str]]:
    prompt = await get_prompt(session, prompt_key)
    effective_version = version or prompt.default_version
    prompt_version = await get_prompt_version(session, prompt_key, effective_version)

    if env == "prod" and version is None and prompt_version.status != "published":
        raise APIError(
            status_code=400,
            code="PROMPT_VERSION_NOT_PUBLISHED",
            message="Prompt version is not published",
            details={"prompt_key": prompt_key, "version": effective_version},
        )

    missing = [name for name in _required_variables(prompt_version.variables_schema) if name not in variables]
    if missing:
        await _log_render(
            session,
            trace_id,
            project_id,
            env,
            prompt_key,
            effective_version,
            variables,
            "failed",
            f"Missing variables: {', '.join(missing)}",
        )
        raise APIError(
            status_code=400,
            code="PROMPT_VARIABLE_MISSING",
            message="Prompt required variables are missing",
            details={"missing": missing},
        )

    variables_used = VARIABLE_PATTERN.findall(prompt_version.content)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = variables.get(name, "")
        return str(value)

    rendered = VARIABLE_PATTERN.sub(replace, prompt_version.content)
    await _log_render(
        session,
        trace_id,
        project_id,
        env,
        prompt_key,
        effective_version,
        variables,
        "success",
        None,
    )
    return effective_version, rendered, variables_used


async def _log_render(
    session: AsyncSession,
    trace_id: str,
    project_id: str,
    env: str,
    prompt_key: str,
    version: str,
    variables: dict[str, Any],
    status: str,
    error_message: str | None,
) -> None:
    session.add(
        PromptRenderLog(
            trace_id=trace_id,
            project_id=project_id,
            env=env,
            prompt_key=prompt_key,
            version=version,
            variables_hash=_variables_hash(variables),
            status=status,
            error_message=error_message,
        )
    )
    await session.commit()
