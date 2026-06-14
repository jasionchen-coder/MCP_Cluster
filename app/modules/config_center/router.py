from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.config_center.schemas import (
    ConfigChangeLogList,
    ConfigChangeLogResponse,
    TaskConfigResponse,
    TaskConfigUpsert,
)
from app.modules.config_center.service import (
    get_task_config,
    list_change_logs,
    upsert_task_config,
)
from app.shared.database import get_session
from app.shared.tracing import get_trace_id

router = APIRouter(prefix="/api/v1/configs", tags=["config-center"])


@router.get("/{project_id}/{env}/tasks/{task_type}", response_model=TaskConfigResponse)
async def read_task_config(
    project_id: str,
    env: str,
    task_type: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TaskConfigResponse:
    config = await get_task_config(session, project_id, env, task_type)
    return TaskConfigResponse(**config.as_dict(), trace_id=get_trace_id(request))


@router.put("/{project_id}/{env}/tasks/{task_type}", response_model=TaskConfigResponse)
async def write_task_config(
    project_id: str,
    env: str,
    task_type: str,
    payload: TaskConfigUpsert,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TaskConfigResponse:
    config = await upsert_task_config(session, project_id, env, task_type, payload)
    return TaskConfigResponse(**config.as_dict(), trace_id=get_trace_id(request))


@router.get("/change-logs", response_model=ConfigChangeLogList)
async def read_change_logs(
    project_id: str | None = None,
    env: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> ConfigChangeLogList:
    logs = await list_change_logs(session, project_id=project_id, env=env)
    return ConfigChangeLogList(
        items=[
            ConfigChangeLogResponse(
                id=log.id,
                project_id=log.project_id,
                env=log.env,
                config_type=log.config_type,
                config_key=log.config_key,
                before_value=log.before_value,
                after_value=log.after_value,
                changed_by=log.changed_by,
            )
            for log in logs
        ]
    )
