from pydantic import BaseModel, Field


class SecretUpsert(BaseModel):
    secret_value: str = Field(min_length=1)
    description: str | None = None
    enabled: bool = True


class SecretMetadataResponse(BaseModel):
    project_id: str
    env: str
    secret_key: str
    secret_ref: str
    description: str | None = None
    version: int
    enabled: bool
    value_fingerprint: str
    created_at: str
    updated_at: str
    trace_id: str | None = None


class SecretListResponse(BaseModel):
    items: list[SecretMetadataResponse]


class SecretResolveResponse(BaseModel):
    project_id: str
    env: str
    secret_key: str
    secret_value: str
    version: int
    trace_id: str | None = None
