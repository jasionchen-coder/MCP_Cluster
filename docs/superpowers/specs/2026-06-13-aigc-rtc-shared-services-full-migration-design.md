# 智能客服共享服务完整迁移设计

## 范围

本阶段把 `D:\Code\LangChain\LLMServer` 除会话历史外的共享能力迁到 `D:\Code\MCP_Cluster`：

- Config Center
- Prompt Registry
- RAG Service
- LLM Gateway（已完成，本阶段补齐配置化）

`LLMServer` 对外 HTTP 契约保持不变，RTC、前端、`Server_py` 不需要改。

## PostgreSQL 存储

共享知识库落在 MCP_Cluster 的数据库里。MCP_Cluster 已通过 `DATABASE_URL` 支持 SQLAlchemy async 数据库配置，生产/联调时使用本地 PostgreSQL：

```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mcp_shared_services
```

RAG V1 继续使用当前表结构存储 knowledge base、documents、chunks、retrieval logs 和 evidence packs。向量检索不在本阶段实现。

## 数据流

```text
LLMServer /v1/chat/completions
  -> Config Center: aigc_rtc/dev/voice_dialogue
  -> RAG Service: rag_policy_id 作为 kb_id 检索
  -> Prompt Registry: 渲染命中/未命中/基础人设 Prompt
  -> LLM Gateway: 使用 model_policy_id 调模型
  -> LLMServer: 保持 SSE、OpenAI-compatible 响应和本地会话历史
```

## Config Center

`aigc_rtc/dev/voice_dialogue` 配置：

- `prompt_key`: `aigc.voice.persona.default`
- `prompt_version`: `v1`
- `model_policy_id`: `voice_low_latency`
- `rag_enabled`: `true`
- `rag_policy_id`: `aigc_voice_kb`

## Prompt Registry

新增三个智能客服 Prompt：

- `aigc.voice.persona.default`: session 创建时的基础人设。
- `aigc.voice.rag.with_context`: RAG 命中时的 system prompt，变量 `context`。
- `aigc.voice.rag.no_context`: RAG 未命中时的 system prompt。

## RAG Service

新增 seed：

- knowledge base: `aigc_voice_kb`
- 示例文档：退款政策、人工客服转接等本地测试材料

智能客服开启 `SHARED_PLATFORM_ENABLED=true` 时，`/debug/rag`、`/debug/search` 和正常对话都走 MCP_Cluster RAG。

## 回退策略

`SHARED_PLATFORM_ENABLED=false` 时：

- Prompt 继续用 `rag/prompt.py`
- RAG 继续用火山知识库 `knowledge_base/viking_kb.py`
- LLM 继续直连 Ark

共享平台开启后，如果 Config/Prompt/RAG 调用失败，接口返回错误或走现有错误路径，不静默伪造知识库结果。

