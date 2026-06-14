from typing import Any

from pydantic import BaseModel


class TaskConfigUpsert(BaseModel):
    prompt_key: str
    prompt_version: str
    model_policy_id: str
    rag_enabled: bool = False
    rag_policy_id: str | None = None
    enabled: bool = True


class TaskConfigResponse(TaskConfigUpsert):
    project_id: str
    env: str
    task_type: str
    trace_id: str


class ConfigChangeLogResponse(BaseModel):
    id: int
    project_id: str
    env: str
    config_type: str
    config_key: str
    before_value: dict[str, Any] | None
    after_value: dict[str, Any]
    changed_by: str


class ConfigChangeLogList(BaseModel):
    items: list[ConfigChangeLogResponse]
