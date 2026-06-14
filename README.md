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
- Secret Manager V1
- Tool Registry V1
- MCP Server wrapper

## Secret Manager

Secret Manager 用于按项目和环境加密保存敏感配置，例如模型 API Key、RTC AppKey、外部工具凭证。

生产环境应配置稳定的加密密钥：

```powershell
$env:SECRET_ENCRYPTION_KEY="your-stable-secret-key"
```

也可以使用 Fernet key。未配置时会使用本地开发兜底密钥，适合开发联调，不适合生产。

HTTP 接口：

- `PUT /api/v1/secrets/{project_id}/{env}/{secret_key}`：新增或更新 secret
- `GET /api/v1/secrets/{project_id}/{env}/{secret_key}`：读取 secret 元数据，不返回明文
- `GET /api/v1/secrets?project_id=...&env=...`：查询 secret 元数据列表
- `POST /api/v1/secrets/{project_id}/{env}/{secret_key}/resolve`：解析 secret 明文，供受控服务端调用

普通元数据响应会返回 `secret_ref`，例如：

```text
secret://finance_media/dev/ark_api_key
```

后续 Tool Registry 和 Agent Gateway 可以保存这个引用，而不是保存明文。

## Tool Registry

Tool Registry 用于按项目和环境登记可供 Agent 使用的工具目录。它只保存工具元数据和凭证引用，不负责直接执行工具。

适合登记的工具类型：

- `http`：外部或内部 HTTP API
- `mcp`：MCP Server 暴露的工具
- `builtin`：平台内置工具或后续 Agent Gateway 内部能力

核心字段：

- `endpoint_config`：工具连接信息，例如 HTTP URL、方法，或 MCP server/tool 名称
- `input_schema` / `output_schema`：工具输入输出结构
- `auth_type`：`none`、`api_key`、`bearer`、`basic`、`custom`
- `secret_ref`：Secret Manager 返回的引用，例如 `secret://finance_media/dev/news_api_token`
- `permission_scope`：`private`、`project`、`public`
- `tags`：工具标签，便于 Agent 按任务筛选

HTTP 接口：

- `PUT /api/v1/tools/{project_id}/{env}/{tool_id}`：新增或更新工具定义
- `GET /api/v1/tools/{project_id}/{env}/{tool_id}`：读取工具定义
- `GET /api/v1/tools?project_id=...&env=...&tool_type=...&enabled=true&tag=...`：查询工具列表

## MCP Server

四个共享 HTTP 服务也暴露为 MCP 工具，默认通过 Streamable HTTP 启动，使用独立端口 `8401`：

```powershell
uv --cache-dir .uv-cache run python -m app.mcp_server
```

默认地址：

```text
http://127.0.0.1:8401/mcp
```

MCP Streamable HTTP Host 配置示例：

```json
{
  "mcpServers": {
    "mcp-shared-services": {
      "url": "http://127.0.0.1:8401/mcp"
    }
  }
}
```

如果需要改端口：

```powershell
$env:MCP_PORT="8401"
uv --cache-dir .uv-cache run python -m app.mcp_server
```

如果需要 stdio 模式，可以显式指定：

```powershell
$env:MCP_TRANSPORT="stdio"
uv --cache-dir .uv-cache run python -m app.mcp_server
```

当前工具覆盖：

- Secret Manager：`secret_upsert`、`secret_get_metadata`、`secret_list`、`secret_resolve`
- Tool Registry：`tool_registry_upsert`、`tool_registry_get`、`tool_registry_list`
- Config Center：`config_get_task`、`config_upsert_task`、`config_list_change_logs`
- Prompt Registry：`prompt_create`、`prompt_create_version`、`prompt_publish_version`、`prompt_render`
- RAG Service：`rag_create_knowledge_base`、`rag_ingest_document`、`rag_search`、`rag_create_evidence_pack`
- LLM Gateway：`llm_generate`、`llm_json_generate`、`llm_image_generate`

## 下游项目共享平台地址

本地开发统一使用 `http://localhost:8400` 作为 MCP_Cluster 共享平台地址，避免和营销项目 `backend_api:8000` 冲突。

- 营销内容编排：`SHARED_PLATFORM_BASE_URL=http://localhost:8400`
- 智能客服 LLMServer：`SHARED_PLATFORM_BASE_URL=http://localhost:8400`

如果使用 PostgreSQL 并已安装 `pgvector`，启动或 seed 时会自动执行：

- `CREATE EXTENSION IF NOT EXISTS vector`
- 为 `rag_chunks` 增加 `embedding_vector vector(...)`
- 回填已有 chunk 的向量并优先走 pgvector 检索
