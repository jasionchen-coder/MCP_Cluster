from fastapi.testclient import TestClient

from app.main import app


def test_prompt_can_be_created_published_and_rendered():
    with TestClient(app) as client:
        prompt_response = client.post(
            "/api/v1/prompts",
            json={
                "project_id": "finance_media",
                "prompt_key": "finance.article.draft",
                "name": "金融文章生成 Prompt",
                "description": "用于根据选题和证据材料生成长文",
                "default_version": "v1",
            },
        )

        assert prompt_response.status_code == 200
        assert prompt_response.json()["prompt_key"] == "finance.article.draft"

        version_response = client.post(
            "/api/v1/prompts/finance.article.draft/versions",
            json={
                "version": "v1",
                "content": "选题：{{topic}}\n证据：{{evidence}}\n受众：{{target_audience}}",
                "variables_schema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "evidence": {"type": "string"},
                        "target_audience": {"type": "string"},
                    },
                    "required": ["topic", "evidence"],
                },
                "status": "draft",
            },
        )

        assert version_response.status_code == 200
        assert version_response.json()["status"] == "draft"

        publish_response = client.post("/api/v1/prompts/finance.article.draft/versions/v1/publish")

        assert publish_response.status_code == 200
        assert publish_response.json()["status"] == "published"

        render_response = client.post(
            "/api/v1/prompts/render",
            json={
                "project_id": "finance_media",
                "env": "prod",
                "prompt_key": "finance.article.draft",
                "variables": {
                    "topic": "今日金融市场热点",
                    "evidence": "RAG 证据材料",
                    "target_audience": "普通投资者",
                },
                "trace_id": "trace_prompt_test",
            },
        )

        assert render_response.status_code == 200
        assert render_response.json()["version"] == "v1"
        assert render_response.json()["trace_id"] == "trace_prompt_test"
        assert "今日金融市场热点" in render_response.json()["rendered_content"]
        assert render_response.json()["variables_used"] == [
            "topic",
            "evidence",
            "target_audience",
        ]


def test_prompt_render_missing_required_variable_returns_standard_error():
    with TestClient(app) as client:
        client.post(
            "/api/v1/prompts",
            json={
                "project_id": "finance_media",
                "prompt_key": "finance.article.draft",
                "name": "金融文章生成 Prompt",
                "description": "用于根据选题和证据材料生成长文",
                "default_version": "v1",
            },
        )
        client.post(
            "/api/v1/prompts/finance.article.draft/versions",
            json={
                "version": "v1",
                "content": "选题：{{topic}}\n证据：{{evidence}}",
                "variables_schema": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "evidence": {"type": "string"},
                    },
                    "required": ["topic", "evidence"],
                },
                "status": "published",
            },
        )
        response = client.post(
            "/api/v1/prompts/render",
            json={
                "project_id": "finance_media",
                "env": "dev",
                "prompt_key": "finance.article.draft",
                "version": "v1",
                "variables": {"topic": "今日金融市场热点"},
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PROMPT_VARIABLE_MISSING"
    assert response.json()["error"]["details"]["missing"] == ["evidence"]
