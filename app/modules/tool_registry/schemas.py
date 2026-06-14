from typing import Any, Literal

from pydantic import BaseModel, Field

ToolType = Literal["http", "mcp", "builtin"]
AuthType = Literal["none", "api_key", "bearer", "basic", "custom"]
PermissionScope = Literal["private", "project", "public"]


class ToolUpsert(BaseModel):
    display_name: str
    description: str | None = None
    tool_type: ToolType
    endpoint_config: dict[str, Any] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    auth_type: AuthType = "none"
    secret_ref: str | None = None
    permission_scope: PermissionScope = "project"
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class ToolResponse(ToolUpsert):
    project_id: str
    env: str
    tool_id: str
    version: int
    created_at: str
    updated_at: str
    trace_id: str | None = None


class ToolListResponse(BaseModel):
    items: list[ToolResponse]
