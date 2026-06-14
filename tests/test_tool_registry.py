from fastapi.testclient import TestClient

from app.main import app


def test_tool_can_be_registered_read_and_updated():
    with TestClient(app) as client:
        create_response = client.put(
            "/api/v1/tools/finance_media/dev/market_news_search",
            json={
                "display_name": "Market News Search",
                "description": "Search latest market news.",
                "tool_type": "http",
                "endpoint_config": {
                    "method": "POST",
                    "url": "https://example.test/news/search",
                    "timeout_seconds": 10,
                },
                "input_schema": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {"query": {"type": "string"}},
                },
                "output_schema": {"type": "object"},
                "auth_type": "bearer",
                "secret_ref": "secret://finance_media/dev/news_api_token",
                "permission_scope": "project",
                "tags": ["news", "finance"],
                "enabled": True,
            },
            headers={"x-trace-id": "trace_tool_test"},
        )

        assert create_response.status_code == 200
        body = create_response.json()
        assert body["tool_id"] == "market_news_search"
        assert body["tool_type"] == "http"
        assert body["secret_ref"] == "secret://finance_media/dev/news_api_token"
        assert body["version"] == 1
        assert body["trace_id"] == "trace_tool_test"

        read_response = client.get("/api/v1/tools/finance_media/dev/market_news_search")
        assert read_response.status_code == 200
        assert read_response.json()["endpoint_config"]["method"] == "POST"

        update_response = client.put(
            "/api/v1/tools/finance_media/dev/market_news_search",
            json={
                "display_name": "Market News Search",
                "description": "Search market news through the approved provider.",
                "tool_type": "http",
                "endpoint_config": {"method": "POST", "url": "https://example.test/v2/news/search"},
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "auth_type": "bearer",
                "secret_ref": "secret://finance_media/dev/news_api_token",
                "permission_scope": "project",
                "tags": ["news", "finance", "approved"],
                "enabled": True,
            },
        )

        assert update_response.status_code == 200
        assert update_response.json()["version"] == 2
        assert update_response.json()["description"] == "Search market news through the approved provider."


def test_tool_list_supports_filters():
    with TestClient(app) as client:
        client.put(
            "/api/v1/tools/finance_media/dev/market_news_search",
            json={
                "display_name": "Market News Search",
                "tool_type": "http",
                "endpoint_config": {"url": "https://example.test/news/search"},
                "tags": ["news", "finance"],
                "enabled": True,
            },
        )
        client.put(
            "/api/v1/tools/finance_media/dev/render_prompt",
            json={
                "display_name": "Render Prompt",
                "tool_type": "mcp",
                "endpoint_config": {"server": "mcp-shared-services", "tool": "prompt_render"},
                "tags": ["prompt"],
                "enabled": False,
            },
        )

        http_response = client.get("/api/v1/tools?project_id=finance_media&env=dev&tool_type=http")
        assert http_response.status_code == 200
        assert [item["tool_id"] for item in http_response.json()["items"]] == ["market_news_search"]

        enabled_response = client.get("/api/v1/tools?project_id=finance_media&env=dev&enabled=true")
        assert enabled_response.status_code == 200
        assert [item["tool_id"] for item in enabled_response.json()["items"]] == ["market_news_search"]

        tag_response = client.get("/api/v1/tools?project_id=finance_media&env=dev&tag=prompt")
        assert tag_response.status_code == 200
        assert [item["tool_id"] for item in tag_response.json()["items"]] == ["render_prompt"]


def test_invalid_tool_type_is_rejected():
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/tools/finance_media/dev/bad_tool",
            json={
                "display_name": "Bad Tool",
                "tool_type": "ftp",
            },
        )

    assert response.status_code == 422


def test_missing_tool_returns_standard_error():
    with TestClient(app) as client:
        response = client.get("/api/v1/tools/finance_media/dev/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TOOL_NOT_FOUND"
