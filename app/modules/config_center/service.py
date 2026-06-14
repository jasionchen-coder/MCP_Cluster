from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.config_center.models import ConfigChangeLog, TaskConfig
from app.modules.config_center.schemas import TaskConfigUpsert
from app.shared.errors import APIError


async def get_task_config(
    session: AsyncSession,
    project_id: str,
    env: str,
    task_type: str,
) -> TaskConfig:
    stmt = select(TaskConfig).where(
        TaskConfig.project_id == project_id,
        TaskConfig.env == env,
        TaskConfig.task_type == task_type,
    )
    config = (await session.execute(stmt)).scalar_one_or_none()
    if config is None:
        raise APIError(
            status_code=404,
            code="CONFIG_NOT_FOUND",
            message="Task config not found",
            details={"project_id": project_id, "env": env, "task_type": task_type},
        )
    return config


async def upsert_task_config(
    session: AsyncSession,
    project_id: str,
    env: str,
    task_type: str,
    payload: TaskConfigUpsert,
) -> TaskConfig:
    before_value = None
    try:
        config = await get_task_config(session, project_id, env, task_type)
        before_value = config.as_dict()
        for key, value in payload.model_dump().items():
            setattr(config, key, value)
    except APIError:
        config = TaskConfig(
            project_id=project_id,
            env=env,
            task_type=task_type,
            **payload.model_dump(),
        )
        session.add(config)

    await session.flush()
    log = ConfigChangeLog(
        project_id=project_id,
        env=env,
        config_type="task",
        config_key=task_type,
        before_value=before_value,
        after_value=config.as_dict(),
    )
    session.add(log)
    await session.commit()
    await session.refresh(config)
    return config


async def list_change_logs(
    session: AsyncSession,
    project_id: str | None = None,
    env: str | None = None,
) -> list[ConfigChangeLog]:
    stmt: Select[tuple[ConfigChangeLog]] = select(ConfigChangeLog).order_by(ConfigChangeLog.id)
    if project_id:
        stmt = stmt.where(ConfigChangeLog.project_id == project_id)
    if env:
        stmt = stmt.where(ConfigChangeLog.env == env)
    return list((await session.execute(stmt)).scalars().all())
