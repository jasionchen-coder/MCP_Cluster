# MCP 共享服务 V1 设计

## 范围

在 `D:\Code\MCP_Cluster` 中建设第一版共享 AI 服务平台。

第一版采用一个模块化 FastAPI 应用，而不是四个独立部署的服务。它为两个现有项目提供稳定的 HTTP 接口：

- 智能客服 / RTC 项目：`D:\Code\LangChain`
- 金融内容编排项目：`D:\Code\Media_Agent\financial_agent_project`

第一轮实现重点包括：

- Config Center
- Prompt Registry
- LLM Gateway
- RAG Service 的 API 和元数据模型

向量检索、两个业务项目的完整接入、管理后台、MCP 封装和生产级权限系统暂不纳入第一轮。

## 推荐方案

使用模块化单体架构：

```text
app/
  main.py
  modules/
    config_center/
    prompt_registry/
    llm_gateway/
    rag_service/
  shared/
    config.py
    database.py
    errors.py
    tracing.py
    time.py
tests/
scripts/
migrations/
```

这个方案符合原技术文档的方向，同时降低第一版的部署和协作成本。每个模块独立拥有自己的路由、Schema、数据模型和业务逻辑，后续可以平滑拆分为独立服务。

## 架构

平台统一在 `/api/v1` 下暴露 REST API。

Config Center 负责回答某个任务应该使用哪个 Prompt、模型策略和 RAG 策略。

Prompt Registry 负责存储 Prompt 模板、版本和发布状态，支持渲染 `{{variable}}` 模板、校验必填变量，并记录渲染日志。

LLM Gateway 通过 OpenAI-compatible 客户端路由模型请求，记录延迟和 token 用量，支持普通生成、流式生成和 JSON 结构化生成，并返回统一错误结构。

RAG Service V1 存储知识库、文档、chunk、检索日志和 evidence pack 元数据。第一版支持文档入库、确定性的固定切块，以及基于已存储 chunk 的项目隔离文本检索。Embedding 和 pgvector/Qdrant 先通过向量后端接口预留，实际接入后置。

## 数据存储

使用 SQLAlchemy 2 async。生产目标数据库为 PostgreSQL。

本地测试使用 `sqlite+aiosqlite`，这样核心行为不依赖 Docker 或外部服务即可验证。

从第一版开始引入 Alembic，方便数据库结构稳定后生成 PostgreSQL 迁移。

## API 范围

健康检查：

- `GET /healthz`

Config Center:

- `GET /api/v1/configs/{project_id}/{env}/tasks/{task_type}`
- `PUT /api/v1/configs/{project_id}/{env}/tasks/{task_type}`
- `GET /api/v1/configs/change-logs`

Prompt Registry:

- `POST /api/v1/prompts`
- `POST /api/v1/prompts/{prompt_key}/versions`
- `POST /api/v1/prompts/{prompt_key}/versions/{version}/publish`
- `POST /api/v1/prompts/render`

LLM Gateway:

- `POST /api/v1/llm/generate`
- `POST /api/v1/llm/stream`
- `POST /api/v1/llm/json-generate`
- `POST /v1/chat/completions`

其中 `/v1/chat/completions` 是兼容入口，用于适配智能客服项目。该项目当前的 `LLMServer` 已经暴露 OpenAI-compatible chat 路由。

RAG Service:

- `POST /api/v1/rag/knowledge-bases`
- `POST /api/v1/rag/documents`
- `POST /api/v1/rag/search`
- `POST /api/v1/rag/evidence-pack`

## Trace 与错误结构

每个请求都必须有 trace ID。

如果调用方在 JSON body 中传入 `trace_id`，服务继续使用该值。否则 middleware 自动生成 `trace_<uuid>`。

错误响应统一使用：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  },
  "trace_id": "trace_xxx"
}
```

## 现有项目适配

### 智能客服 / RTC 项目

共享平台必须保留 OpenAI-compatible chat 行为，方便现有 RTC 服务从 `D:\Code\LangChain\LLMServer` 渐进迁移。

第一轮接入目标只放在 LLM 调用链路上。上下文 / 会话持久化，以及 RTC、ASR、TTS 链路继续保留在原项目中。

### 金融内容编排项目

共享平台与当前金融项目的最佳接入点是 `ai_service/tools/llm_client.py`。

第一轮接入目标是把直接调用 Ark 的逻辑替换为调用共享 LLM Gateway，同时保持 LangGraph 节点不变。之后可以继续在同一个 client wrapper 内引入 Prompt Registry 和 Config Center 调用。

当前 Brave MCP 搜索链路不应直接等同于 RAG。它提供的是实时新闻搜索能力；RAG V1 提供的是已入库知识检索和 evidence pack。

## 测试

使用 pytest，并启用 async 测试支持。

初始测试覆盖：

- `/healthz`
- Config 创建、读取和 change log
- Prompt 创建、发布、渲染，以及缺少变量错误
- LLM Gateway 策略查询和 mocked provider 调用
- JSON 生成结果 Schema 校验
- RAG 知识库创建、文档切块、同项目检索、跨项目拒绝
- Trace ID 传递和统一错误响应

单元测试中 mock 外部 Ark 调用。真实模型调用只放在 smoke test 中。

## 暂缓内容

- 真实向量后端接入
- 两个现有项目的完整接入改造
- 管理后台
- 超出 project/env 隔离校验的认证与授权
- MCP tool 封装
- 成本看板
- Prompt 可视化编辑器
- 多租户权限审批流程

## 验收标准

- 服务可以在本地启动。
- `/healthz` 返回 ok。
- Swagger 可以访问。
- Config Center 可以初始化并读取 `finance_media/dev/generate_article` 和 `aigc_rtc/dev/voice_dialogue`。
- Prompt Registry 可以渲染 `finance.article.draft`，缺少必填变量时返回 `PROMPT_VARIABLE_MISSING`。
- LLM Gateway 可以调用注入的 OpenAI-compatible provider client，并记录 invocation logs。
- RAG V1 默认禁止跨项目访问知识库。
- 所有公开响应都包含 trace ID。
