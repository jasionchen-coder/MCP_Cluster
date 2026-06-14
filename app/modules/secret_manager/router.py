from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.secret_manager.schemas import (
    SecretListResponse,
    SecretMetadataResponse,
    SecretResolveResponse,
    SecretUpsert,
)
from app.modules.secret_manager.service import (
    get_secret_metadata,
    list_secrets,
    resolve_secret_value,
    upsert_secret,
)
from app.shared.database import get_session
from app.shared.tracing import get_trace_id

router = APIRouter(prefix="/api/v1/secrets", tags=["secret-manager"])


def _metadata_response(secret, trace_id: str | None = None) -> SecretMetadataResponse:
    return SecretMetadataResponse(**secret.metadata_dict(), trace_id=trace_id)


@router.put("/{project_id}/{env}/{secret_key}", response_model=SecretMetadataResponse)
async def write_secret(
    project_id: str,
    env: str,
    secret_key: str,
    payload: SecretUpsert,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SecretMetadataResponse:
    secret = await upsert_secret(session, project_id, env, secret_key, payload)
    return _metadata_response(secret, get_trace_id(request))


@router.get("/{project_id}/{env}/{secret_key}", response_model=SecretMetadataResponse)
async def read_secret_metadata(
    project_id: str,
    env: str,
    secret_key: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SecretMetadataResponse:
    secret = await get_secret_metadata(session, project_id, env, secret_key)
    return _metadata_response(secret, get_trace_id(request))


@router.get("", response_model=SecretListResponse)
async def read_secrets(
    project_id: str | None = None,
    env: str | None = None,
    enabled: bool | None = None,
    session: AsyncSession = Depends(get_session),
) -> SecretListResponse:
    secrets = await list_secrets(session, project_id=project_id, env=env, enabled=enabled)
    return SecretListResponse(items=[_metadata_response(secret) for secret in secrets])


@router.post("/{project_id}/{env}/{secret_key}/resolve", response_model=SecretResolveResponse)
async def resolve_secret(
    project_id: str,
    env: str,
    secret_key: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SecretResolveResponse:
    secret, secret_value = await resolve_secret_value(session, project_id, env, secret_key)
    return SecretResolveResponse(
        project_id=project_id,
        env=env,
        secret_key=secret_key,
        secret_value=secret_value,
        version=secret.version,
        trace_id=get_trace_id(request),
    )
