import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.secret_manager.models import ManagedSecret
from app.modules.secret_manager.schemas import SecretUpsert
from app.shared.config import get_settings
from app.shared.errors import APIError


def _derive_fernet_key(raw_key: str) -> bytes:
    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def _get_fernet() -> Fernet:
    raw_key = get_settings().secret_encryption_key or "mcp-shared-services-local-secret-key"
    try:
        return Fernet(raw_key.encode("utf-8"))
    except (ValueError, TypeError):
        return Fernet(_derive_fernet_key(raw_key))


def encrypt_secret(secret_value: str) -> str:
    return _get_fernet().encrypt(secret_value.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_value: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise APIError(
            status_code=500,
            code="SECRET_DECRYPT_FAILED",
            message="Secret cannot be decrypted with the configured key",
            details={},
        ) from exc


def fingerprint_secret(secret_value: str) -> str:
    return hashlib.sha256(secret_value.encode("utf-8")).hexdigest()


async def upsert_secret(
    session: AsyncSession,
    project_id: str,
    env: str,
    secret_key: str,
    payload: SecretUpsert,
) -> ManagedSecret:
    existing = await find_secret(session, project_id, env, secret_key, require_enabled=False)
    encrypted_value = encrypt_secret(payload.secret_value)
    value_fingerprint = fingerprint_secret(payload.secret_value)
    if existing is None:
        secret = ManagedSecret(
            project_id=project_id,
            env=env,
            secret_key=secret_key,
            encrypted_value=encrypted_value,
            value_fingerprint=value_fingerprint,
            description=payload.description,
            enabled=payload.enabled,
        )
        session.add(secret)
    else:
        secret = existing
        secret.encrypted_value = encrypted_value
        secret.value_fingerprint = value_fingerprint
        secret.description = payload.description
        secret.enabled = payload.enabled
        secret.version += 1
    await session.commit()
    await session.refresh(secret)
    return secret


async def find_secret(
    session: AsyncSession,
    project_id: str,
    env: str,
    secret_key: str,
    *,
    require_enabled: bool = True,
) -> ManagedSecret | None:
    stmt = select(ManagedSecret).where(
        ManagedSecret.project_id == project_id,
        ManagedSecret.env == env,
        ManagedSecret.secret_key == secret_key,
    )
    if require_enabled:
        stmt = stmt.where(ManagedSecret.enabled.is_(True))
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_secret_metadata(
    session: AsyncSession,
    project_id: str,
    env: str,
    secret_key: str,
) -> ManagedSecret:
    secret = await find_secret(session, project_id, env, secret_key, require_enabled=False)
    if secret is None:
        raise APIError(
            status_code=404,
            code="SECRET_NOT_FOUND",
            message="Secret not found",
            details={"project_id": project_id, "env": env, "secret_key": secret_key},
        )
    return secret


async def list_secrets(
    session: AsyncSession,
    project_id: str | None = None,
    env: str | None = None,
    enabled: bool | None = None,
) -> list[ManagedSecret]:
    stmt: Select[tuple[ManagedSecret]] = select(ManagedSecret).order_by(
        ManagedSecret.project_id,
        ManagedSecret.env,
        ManagedSecret.secret_key,
    )
    if project_id:
        stmt = stmt.where(ManagedSecret.project_id == project_id)
    if env:
        stmt = stmt.where(ManagedSecret.env == env)
    if enabled is not None:
        stmt = stmt.where(ManagedSecret.enabled.is_(enabled))
    return list((await session.execute(stmt)).scalars().all())


async def resolve_secret_value(
    session: AsyncSession,
    project_id: str,
    env: str,
    secret_key: str,
) -> tuple[ManagedSecret, str]:
    secret = await find_secret(session, project_id, env, secret_key, require_enabled=True)
    if secret is None:
        raise APIError(
            status_code=404,
            code="SECRET_NOT_FOUND",
            message="Secret not found or disabled",
            details={"project_id": project_id, "env": env, "secret_key": secret_key},
        )
    return secret, decrypt_secret(secret.encrypted_value)


def secret_ref(project_id: str, env: str, secret_key: str) -> str:
    return f"secret://{project_id}/{env}/{secret_key}"
