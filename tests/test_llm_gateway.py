import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.modules.llm_gateway.models import (
    LLMInvocationLog,
    LLMModelEndpoint,
    LLMModelPolicy,
    LLMModelProvider,
)
from app.modules.llm_gateway.provider import ProviderResult, set_provider
from app.shared.database import SessionLocal


class FakeProvider:
    async def generate(self, *, model: str, messages: list[dict], temperature: float, max_tokens: int | None, tools: list[dict] | None = None, tool_choice: str | None = None):
        return ProviderResult(
            model=model,
            content='{"passed": true, "feedback": "ok"}',
            usage={"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
            finish_reason="stop",
        )


async def _seed_policy(policy_id: str = "finance_high_quality") -> None:
    async with SessionLocal() as session:
        provider = LLMModelProvider(
            provider_name="fake",
            base_url="https://fake.local/v1",
            api_key_env="FAKE_API_KEY",
            enabled=True,
        )
        session.add(provider)
        await session.flush()
        endpoint = LLMModelEndpoint(
            provider_id=provider.id,
            model_name="fake-model",
            endpoint_id="fake-endpoint",
            supports_stream=True,
            supports_json=True,
            max_context_tokens=8192,
            enabled=True,
        )
        session.add(endpoint)
        await session.flush()
        session.add(
            LLMModelPolicy(
                policy_id=policy_id,
                project_id="finance_media",
                env="dev",
                task_type="generate_article",
                primary_model_id=endpoint.id,
                fallback_model_id=None,
                timeout_ms=30000,
                max_retries=0,
                default_temperature=0.3,
                default_max_tokens=1024,
                enabled=True,
            )
        )
        await session.commit()


def test_generate_uses_policy_provider_and_records_log():
    set_provider(FakeProvider())
    with TestClient(app) as client:
        asyncio.run(_seed_policy())
        response = client.post(
            "/api/v1/llm/generate",
            json={
                "project_id": "finance_media",
                "env": "dev",
                "task_type": "generate_article",
                "model_policy_id": "finance_high_quality",
                "messages": [{"role": "user", "content": "hello"}],
                "trace_id": "trace_llm_test",
            },
        )

    assert response.status_code == 200
    assert response.json()["content"] == '{"passed": true, "feedback": "ok"}'
    assert response.json()["usage"]["total_tokens"] == 5
    assert response.json()["trace_id"] == "trace_llm_test"

    async def fetch_logs():
        async with SessionLocal() as session:
            return list((await session.execute(select(LLMInvocationLog))).scalars().all())

    logs = asyncio.run(fetch_logs())
    assert any(log.trace_id == "trace_llm_test" and log.total_tokens == 5 for log in logs)


def test_json_generate_validates_schema_and_returns_json_content():
    set_provider(FakeProvider())
    with TestClient(app) as client:
        asyncio.run(_seed_policy("finance_json_stable"))
        response = client.post(
            "/api/v1/llm/json-generate",
            json={
                "project_id": "finance_media",
                "env": "dev",
                "task_type": "generate_article",
                "model_policy_id": "finance_json_stable",
                "messages": [{"role": "user", "content": "review"}],
                "json_schema": {
                    "type": "object",
                    "required": ["passed", "feedback"],
                    "properties": {
                        "passed": {"type": "boolean"},
                        "feedback": {"type": "string"},
                    },
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["json_content"] == {"passed": True, "feedback": "ok"}


def test_missing_model_policy_returns_standard_error():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/llm/generate",
            json={
                "project_id": "finance_media",
                "env": "dev",
                "task_type": "generate_article",
                "model_policy_id": "missing",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MODEL_POLICY_NOT_FOUND"


def test_chat_completions_compatibility_route_returns_openai_shape():
    set_provider(FakeProvider())
    with TestClient(app) as client:
        asyncio.run(_seed_policy("compat_policy"))
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "compat_policy",
                "messages": [{"role": "user", "content": "hello"}],
                "project_id": "finance_media",
                "env": "dev",
                "task_type": "generate_article",
            },
        )

    assert response.status_code == 200
    assert response.json()["object"] == "chat.completion"
    assert response.json()["choices"][0]["message"]["content"] == '{"passed": true, "feedback": "ok"}'
