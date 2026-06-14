# MCP Shared Services

模块化单体 FastAPI 共享 AI 服务平台。

## 本地开发

```powershell
uv --cache-dir .uv-cache sync --extra dev --no-managed-python --python D:\sorftWare_package\anaconda\python.exe
uv --cache-dir .uv-cache run python -m pytest -v
uv --cache-dir .uv-cache run uvicorn app.main:app --host 0.0.0.0 --port 8400 --reload
```

初始化开发数据：

```powershell
uv --cache-dir .uv-cache run python -m scripts.seed_dev_data
```

冒烟检查：

```powershell
uv --cache-dir .uv-cache run python -m scripts.smoke_test
uv --cache-dir .uv-cache run python -m scripts.check_pgvector
```

## 当前范围

- Config Center
- Prompt Registry
- LLM Gateway
- RAG Service V1

## 下游项目共享平台地址

本地开发统一使用 `http://localhost:8400` 作为 MCP_Cluster 共享平台地址，避免和营销项目 `backend_api:8000` 冲突。

- 营销内容编排：`SHARED_PLATFORM_BASE_URL=http://localhost:8400`
- 智能客服 LLMServer：`SHARED_PLATFORM_BASE_URL=http://localhost:8400`

如果使用 PostgreSQL 并已安装 `pgvector`，启动或 seed 时会自动执行：

- `CREATE EXTENSION IF NOT EXISTS vector`
- 为 `rag_chunks` 增加 `embedding_vector vector(...)`
- 回填已有 chunk 的向量并优先走 pgvector 检索
