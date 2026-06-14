from typing import Any

from pydantic import BaseModel, Field


class PromptCreate(BaseModel):
    project_id: str
    prompt_key: str
    name: str
    description: str | None = None
    default_version: str
    enabled: bool = True


class PromptResponse(PromptCreate):
    pass


class PromptVersionCreate(BaseModel):
    version: str
    content: str
    variables_schema: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"


class PromptVersionResponse(PromptVersionCreate):
    prompt_key: str


class PromptRenderRequest(BaseModel):
    project_id: str
    env: str
    prompt_key: str
    version: str | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


class PromptRenderResponse(BaseModel):
    prompt_key: str
    version: str
    rendered_content: str
    variables_used: list[str]
    trace_id: str
