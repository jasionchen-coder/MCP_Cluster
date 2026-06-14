import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.modules.secret_manager.models import ManagedSecret
from app.shared.database import SessionLocal


async def _stored_secret() -> ManagedSecret:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(ManagedSecret).where(
                    ManagedSecret.project_id == "finance_media",
                    ManagedSecret.env == "dev",
                    ManagedSecret.secret_key == "ark_api_key",
                )
            )
        ).scalar_one()


def test_secret_can_be_upserted_without_exposing_plaintext():
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/secrets/finance_media/dev/ark_api_key",
            json={
                "secret_value": "sk-test-secret",
                "description": "Ark API key",
                "enabled": True,
            },
            headers={"x-trace-id": "trace_secret_test"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["secret_key"] == "ark_api_key"
        assert body["secret_ref"] == "secret://finance_media/dev/ark_api_key"
        assert body["version"] == 1
        assert body["trace_id"] == "trace_secret_test"
        assert "secret_value" not in body
        assert "encrypted_value" not in body

        stored = asyncio.run(_stored_secret())
        assert stored.encrypted_value != "sk-test-secret"
        assert stored.value_fingerprint

        read_response = client.get("/api/v1/secrets/finance_media/dev/ark_api_key")
        assert read_response.status_code == 200
        assert "secret_value" not in read_response.json()

        list_response = client.get("/api/v1/secrets?project_id=finance_media&env=dev")
        assert list_response.status_code == 200
        assert len(list_response.json()["items"]) == 1
        assert "secret_value" not in list_response.json()["items"][0]


def test_secret_can_be_resolved_and_rotated():
    with TestClient(app) as client:
        create_response = client.put(
            "/api/v1/secrets/finance_media/dev/ark_api_key",
            json={"secret_value": "sk-old", "enabled": True},
        )
        assert create_response.status_code == 200

        update_response = client.put(
            "/api/v1/secrets/finance_media/dev/ark_api_key",
            json={"secret_value": "sk-new", "enabled": True},
        )
        assert update_response.status_code == 200
        assert update_response.json()["version"] == 2

        resolve_response = client.post("/api/v1/secrets/finance_media/dev/ark_api_key/resolve")
        assert resolve_response.status_code == 200
        assert resolve_response.json()["secret_value"] == "sk-new"
        assert resolve_response.json()["version"] == 2


def test_disabled_secret_cannot_be_resolved():
    with TestClient(app) as client:
        create_response = client.put(
            "/api/v1/secrets/finance_media/dev/ark_api_key",
            json={"secret_value": "sk-disabled", "enabled": False},
        )
        assert create_response.status_code == 200

        metadata_response = client.get("/api/v1/secrets/finance_media/dev/ark_api_key")
        assert metadata_response.status_code == 200
        assert metadata_response.json()["enabled"] is False

        resolve_response = client.post("/api/v1/secrets/finance_media/dev/ark_api_key/resolve")
        assert resolve_response.status_code == 404
        assert resolve_response.json()["error"]["code"] == "SECRET_NOT_FOUND"


def test_missing_secret_returns_standard_error():
    with TestClient(app) as client:
        response = client.get("/api/v1/secrets/finance_media/dev/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SECRET_NOT_FOUND"
