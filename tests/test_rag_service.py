from fastapi.testclient import TestClient

from app.main import app


def test_rag_document_ingestion_search_and_evidence_pack():
    with TestClient(app) as client:
        kb_response = client.post(
            "/api/v1/rag/knowledge-bases",
            json={
                "project_id": "finance_media",
                "env": "dev",
                "kb_id": "finance_news_kb",
                "name": "金融新闻知识库",
                "description": "用于金融热点选题和文章生成",
                "permission_scope": "private",
            },
        )

        assert kb_response.status_code == 200
        assert kb_response.json()["collection_name"] == "rag_finance_media_dev"

        doc_response = client.post(
            "/api/v1/rag/documents",
            json={
                "project_id": "finance_media",
                "env": "dev",
                "kb_id": "finance_news_kb",
                "source_type": "manual_text",
                "title": "今日债券市场",
                "content": "今日债券市场关注利率变化。利率下行推动债券价格走强，投资者需要关注久期风险。",
                "metadata": {"source": "manual", "published_at": "2026-06-13"},
            },
        )

        assert doc_response.status_code == 200
        assert doc_response.json()["status"] == "indexed"
        assert doc_response.json()["chunk_count"] >= 1

        search_response = client.post(
            "/api/v1/rag/search",
            json={
                "project_id": "finance_media",
                "env": "dev",
                "kb_ids": ["finance_news_kb"],
                "query": "利率 债券",
                "top_k": 3,
                "trace_id": "trace_rag_test",
            },
        )

        assert search_response.status_code == 200
        assert search_response.json()["trace_id"] == "trace_rag_test"
        assert search_response.json()["results"][0]["kb_id"] == "finance_news_kb"
        assert "债券" in search_response.json()["results"][0]["content"]

        evidence_response = client.post(
            "/api/v1/rag/evidence-pack",
            json={
                "project_id": "finance_media",
                "env": "dev",
                "kb_ids": ["finance_news_kb"],
                "query": "利率 债券",
                "top_k": 3,
            },
        )

        assert evidence_response.status_code == 200
        assert evidence_response.json()["evidence_pack_id"].startswith("evp_")
        assert evidence_response.json()["items"][0]["title"] == "今日债券市场"


def test_rag_cross_project_search_is_denied():
    with TestClient(app) as client:
        client.post(
            "/api/v1/rag/knowledge-bases",
            json={
                "project_id": "finance_media",
                "env": "dev",
                "kb_id": "finance_news_kb",
                "name": "金融新闻知识库",
                "description": "用于金融热点选题和文章生成",
                "permission_scope": "private",
            },
        )
        response = client.post(
            "/api/v1/rag/search",
            json={
                "project_id": "aigc_rtc",
                "env": "dev",
                "kb_ids": ["finance_news_kb"],
                "query": "利率",
                "top_k": 3,
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RAG_ACCESS_DENIED"
