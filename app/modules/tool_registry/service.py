from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tool_registry.models import RegisteredTool
from app.modules.tool_registry.schemas import ToolUpsert
from app.shared.errors import APIError


async def upsert_tool(
    session: AsyncSession,
    project_id: str,
    env: str,
    tool_id: str,
    payload: ToolUpsert,
) -> RegisteredTool:
    tool = await find_tool(session, project_id, env, tool_id, require_enabled=False)
    if tool is None:
        tool = RegisteredTool(
            project_id=project_id,
            env=env,
            tool_id=tool_id,
            **payload.model_dump(),
        )
        session.add(tool)
    else:
        for key, value in payload.model_dump().items():
            setattr(tool, key, value)
        tool.version += 1
    await session.commit()
    await session.refresh(tool)
    return tool


async def find_tool(
    session: AsyncSession,
    project_id: str,
    env: str,
    tool_id: str,
    *,
    require_enabled: bool = True,
) -> RegisteredTool | None:
    stmt = select(RegisteredTool).where(
        RegisteredTool.project_id == project_id,
        RegisteredTool.env == env,
        RegisteredTool.tool_id == tool_id,
    )
    if require_enabled:
        stmt = stmt.where(RegisteredTool.enabled.is_(True))
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_tool(
    session: AsyncSession,
    project_id: str,
    env: str,
    tool_id: str,
    *,
    require_enabled: bool = False,
) -> RegisteredTool:
    tool = await find_tool(session, project_id, env, tool_id, require_enabled=require_enabled)
    if tool is None:
        raise APIError(
            status_code=404,
            code="TOOL_NOT_FOUND",
            message="Tool not found",
            details={"project_id": project_id, "env": env, "tool_id": tool_id},
        )
    return tool


async def list_tools(
    session: AsyncSession,
    project_id: str | None = None,
    env: str | None = None,
    tool_type: str | None = None,
    enabled: bool | None = None,
    tag: str | None = None,
) -> list[RegisteredTool]:
    stmt: Select[tuple[RegisteredTool]] = select(RegisteredTool).order_by(
        RegisteredTool.project_id,
        RegisteredTool.env,
        RegisteredTool.tool_id,
    )
    if project_id:
        stmt = stmt.where(RegisteredTool.project_id == project_id)
    if env:
        stmt = stmt.where(RegisteredTool.env == env)
    if tool_type:
        stmt = stmt.where(RegisteredTool.tool_type == tool_type)
    if enabled is not None:
        stmt = stmt.where(RegisteredTool.enabled.is_(enabled))
    tools = list((await session.execute(stmt)).scalars().all())
    if tag:
        tools = [tool for tool in tools if tag in (tool.tags or [])]
    return tools
