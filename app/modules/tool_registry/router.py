from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tool_registry.schemas import ToolListResponse, ToolResponse, ToolUpsert
from app.modules.tool_registry.service import get_tool, list_tools, upsert_tool
from app.shared.database import get_session
from app.shared.tracing import get_trace_id

router = APIRouter(prefix="/api/v1/tools", tags=["tool-registry"])


def _tool_response(tool, trace_id: str | None = None) -> ToolResponse:
    return ToolResponse(**tool.as_dict(), trace_id=trace_id)


@router.put("/{project_id}/{env}/{tool_id}", response_model=ToolResponse)
async def write_tool(
    project_id: str,
    env: str,
    tool_id: str,
    payload: ToolUpsert,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ToolResponse:
    tool = await upsert_tool(session, project_id, env, tool_id, payload)
    return _tool_response(tool, get_trace_id(request))


@router.get("/{project_id}/{env}/{tool_id}", response_model=ToolResponse)
async def read_tool(
    project_id: str,
    env: str,
    tool_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ToolResponse:
    tool = await get_tool(session, project_id, env, tool_id)
    return _tool_response(tool, get_trace_id(request))


@router.get("", response_model=ToolListResponse)
async def read_tools(
    project_id: str | None = None,
    env: str | None = None,
    tool_type: str | None = None,
    enabled: bool | None = None,
    tag: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> ToolListResponse:
    tools = await list_tools(
        session,
        project_id=project_id,
        env=env,
        tool_type=tool_type,
        enabled=enabled,
        tag=tag,
    )
    return ToolListResponse(items=[_tool_response(tool) for tool in tools])
