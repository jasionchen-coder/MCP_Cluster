from typing import Any

from pydantic import BaseModel, Field


class LLMGenerateRequest(BaseModel):
    project_id: str
    env: str
    task_type: str
    model_policy_id: str
    messages: list[dict[str, Any]]
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | None = None
    trace_id: str | None = None


class ImageGenerateRequest(BaseModel):
    project_id: str
    env: str
    task_type: str
    model_policy_id: str
    prompts: list[str]
    size: str = "2K"
    trace_id: str | None = None


class ImageResultSchema(BaseModel):
    url: str


class ImageGenerateResponse(BaseModel):
    request_id: str
    project_id: str
    task_type: str
    model: str
    images: list[ImageResultSchema]
    latency_ms: int
    trace_id: str | None = None


class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMGenerateResponse(BaseModel):
    request_id: str
    project_id: str
    task_type: str
    model: str
    content: str
    usage: LLMUsage
    latency_ms: int
    finish_reason: str
    tool_calls: list[dict[str, Any]] | None = None
    trace_id: str


class LLMJsonGenerateRequest(LLMGenerateRequest):
    json_schema: dict[str, Any] = Field(default_factory=dict)


class LLMJsonGenerateResponse(LLMGenerateResponse):
    json_content: dict[str, Any]


class ChatCompletionsRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    project_id: str = "default"
    env: str = "dev"
    task_type: str = "chat"
    temperature: float | None = None
    max_tokens: int | None = None
