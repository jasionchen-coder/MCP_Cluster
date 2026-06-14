# 金融项目接入 LLM Gateway 设计

## 范围

本阶段把 `D:\Code\Media_Agent\financial_agent_project` 的文本模型调用接入当前共享平台 `D:\Code\MCP_Cluster` 的 LLM Gateway。

第一阶段只替换非流式文本调用：

- `LLMClient._complete()`
- `LLMClient._complete_json()`

暂不改：

- LangGraph 节点结构
- 本地 YAML Prompt 加载方式
- Brave MCP 搜索链路
- 图片生成链路
- `stream_article()` 的真实流式生成路径

## 目标

金融项目可以通过环境变量切换是否使用共享平台：

- 开启时：本地 Prompt 仍由 YAML 渲染，模型调用走共享平台 HTTP API。
- 关闭时：保持原来的 Ark 直连行为，便于回退。

## 配置

在金融项目 `ai_service/core/config.py` 中新增：

```python
shared_platform_enabled: bool = False
shared_platform_base_url: str = "http://localhost:8000"
shared_platform_project_id: str = "finance_media"
shared_platform_env: str = "dev"
```

对应 `.env`：

```ini
SHARED_PLATFORM_ENABLED=false
SHARED_PLATFORM_BASE_URL=http://localhost:8000
SHARED_PLATFORM_PROJECT_ID=finance_media
SHARED_PLATFORM_ENV=dev
```

## 调用映射

`_complete(prompt_name, **fields)`：

1. 继续从本地 YAML 读取 prompt。
2. 本地渲染 system 和 user。
3. 如果 `shared_platform_enabled=true`，调用：

```http
POST /api/v1/llm/generate
```

4. `model_policy_id` 第一版由 prompt 名映射：

```text
article_reviser -> finance_high_quality
xhs_copy_writer -> finance_high_quality
default -> finance_high_quality
```

`_complete_json(prompt_name, **fields)`：

1. 继续从本地 YAML 读取 prompt。
2. 本地渲染 system 和 user。
3. 如果 `shared_platform_enabled=true`，调用：

```http
POST /api/v1/llm/json-generate
```

4. JSON schema 第一版由 prompt 名映射：

```text
image_prompt_extractor -> {"required": ["prompts"]}
topic_generator -> {"required": ["topics"]}
```

## 数据流

```text
LangGraph node
  -> LLMClient
  -> 本地 Prompt YAML 渲染
  -> SharedPlatformClient
  -> MCP_Cluster LLM Gateway
  -> Ark Provider
  -> 返回 content / json_content / usage
  -> record_token_usage
```

## 错误处理

如果共享平台返回非 2xx：

- 抛出 `RuntimeError`
- 错误信息包含共享平台返回的错误码和 message
- 不静默回退 Ark，避免配置错误被隐藏

如果 `shared_platform_enabled=false`：

- 完全走原逻辑

## 测试

新增或更新金融项目测试：

- shared platform 开启时，`_complete()` 调用 `/api/v1/llm/generate`
- shared platform 开启时，`_complete_json()` 调用 `/api/v1/llm/json-generate`
- usage 会写回现有 metrics
- shared platform 关闭时，原有 mock Ark 测试保持通过

## 验收标准

- 金融项目测试通过。
- 不启动共享平台时，默认行为不变。
- 开启共享平台后，非流式文本任务不再直接调用 Ark SDK。
- `stream_article()` 暂时仍保留原 Ark streaming 路径，并在代码注释中说明后续接入。
