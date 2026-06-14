from fastapi.testclient import TestClient

from app.main import app


def test_task_config_can_be_created_read_updated_and_logged():
    with TestClient(app) as client:
        create_response = client.put(
            "/api/v1/configs/finance_media/dev/tasks/generate_article",
            json={
                "prompt_key": "finance.article.draft",
                "prompt_version": "v1",
                "model_policy_id": "finance_high_quality",
                "rag_enabled": True,
                "rag_policy_id": "finance_news_rag",
                "enabled": True,
            },
            headers={"x-trace-id": "trace_config_test"},
        )

        assert create_response.status_code == 200
        assert create_response.json()["prompt_key"] == "finance.article.draft"
        assert create_response.json()["trace_id"] == "trace_config_test"

        read_response = client.get("/api/v1/configs/finance_media/dev/tasks/generate_article")

        assert read_response.status_code == 200
        assert read_response.json()["project_id"] == "finance_media"
        assert read_response.json()["task_type"] == "generate_article"
        assert read_response.json()["rag_enabled"] is True

        update_response = client.put(
            "/api/v1/configs/finance_media/dev/tasks/generate_article",
            json={
                "prompt_key": "finance.article.draft",
                "prompt_version": "v2",
                "model_policy_id": "finance_high_quality",
                "rag_enabled": False,
                "rag_policy_id": None,
                "enabled": True,
            },
        )

        assert update_response.status_code == 200
        assert update_response.json()["prompt_version"] == "v2"
        assert update_response.json()["rag_enabled"] is False

        logs_response = client.get("/api/v1/configs/change-logs?project_id=finance_media&env=dev")

        assert logs_response.status_code == 200
        logs = logs_response.json()["items"]
        assert len(logs) >= 2
        assert logs[-1]["config_key"] == "generate_article"
        assert logs[-1]["after_value"]["prompt_version"] == "v2"


def test_missing_task_config_returns_standard_error():
    with TestClient(app) as client:
        response = client.get("/api/v1/configs/unknown/dev/tasks/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CONFIG_NOT_FOUND"
    assert response.json()["error"]["details"] == {
        "project_id": "unknown",
        "env": "dev",
        "task_type": "nope",
    }
