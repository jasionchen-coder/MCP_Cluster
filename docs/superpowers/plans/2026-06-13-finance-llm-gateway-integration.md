# Finance LLM Gateway Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让金融内容编排项目可以通过配置切换到 MCP_Cluster 的 LLM Gateway，替代非流式 Ark 直连调用。

**Architecture:** 保留金融项目 LangGraph 节点、本地 YAML Prompt 和 Brave MCP 搜索链路。只在 `LLMClient` 内部增加共享平台 HTTP client，并通过环境变量控制是否启用。

**Tech Stack:** Python、FastAPI 项目现有配置体系、httpx、pytest、pytest-asyncio。

---

### Task 1: Shared Platform 配置

**Files:**
- Modify: `D:\Code\Media_Agent\financial_agent_project\ai_service\core\config.py`
- Modify: `D:\Code\Media_Agent\financial_agent_project\README.md`
- Test: existing settings import through pytest

- [ ] **Step 1: Add settings fields**

Add:

```python
shared_platform_enabled: bool = False
shared_platform_base_url: str = "http://localhost:8000"
shared_platform_project_id: str = "finance_media"
shared_platform_env: str = "dev"
```

- [ ] **Step 2: Document environment variables**

Document:

```ini
SHARED_PLATFORM_ENABLED=false
SHARED_PLATFORM_BASE_URL=http://localhost:8000
SHARED_PLATFORM_PROJECT_ID=finance_media
SHARED_PLATFORM_ENV=dev
```

### Task 2: Shared Platform HTTP Client

**Files:**
- Create: `D:\Code\Media_Agent\financial_agent_project\ai_service\tools\shared_platform_client.py`
- Test: `D:\Code\Media_Agent\financial_agent_project\tests\test_shared_platform_client.py`

- [ ] **Step 1: Write failing tests**

Test that the client posts to `/api/v1/llm/generate` and `/api/v1/llm/json-generate`, returns content/json_content/usage, and raises `RuntimeError` for non-2xx responses.

- [ ] **Step 2: Implement client**

Use `httpx.AsyncClient` with `ASGITransport` support in tests through dependency injection of a custom transport.

### Task 3: LLMClient Integration

**Files:**
- Modify: `D:\Code\Media_Agent\financial_agent_project\ai_service\tools\llm_client.py`
- Test: `D:\Code\Media_Agent\financial_agent_project\tests\test_llm_client_shared_platform.py`

- [ ] **Step 1: Write failing tests**

Test that when `shared_platform_enabled=True`, `_complete()` calls shared `/generate`, `_complete_json()` calls shared `/json-generate`, and usage is recorded.

- [ ] **Step 2: Implement integration**

Add prompt-name mappings:

```python
_MODEL_POLICY_BY_PROMPT = {
    "article_reviser": "finance_high_quality",
    "xhs_copy_writer": "finance_high_quality",
    "image_prompt_extractor": "finance_json_stable",
}
```

Add JSON schema mappings:

```python
_JSON_SCHEMA_BY_PROMPT = {
    "image_prompt_extractor": {
        "type": "object",
        "required": ["prompts"],
        "properties": {"prompts": {"type": "array", "items": {"type": "string"}}},
    }
}
```

If shared platform is disabled, keep existing Ark code path unchanged.

### Task 4: Verification

**Files:**
- All changed files above

- [ ] **Step 1: Run focused tests**

Run:

```powershell
pytest tests/test_shared_platform_client.py tests/test_llm_client_shared_platform.py tests/test_llm_client_xhs.py tests/test_llm_client_topics.py -v
```

- [ ] **Step 2: Run full financial project tests**

Run:

```powershell
pytest -v
```

Expected: all tests pass.

---

## Self-Review

Spec coverage:

- Adds shared platform configuration: Task 1.
- Adds HTTP client: Task 2.
- Switches non-streaming `_complete()` and `_complete_json()`: Task 3.
- Keeps `stream_article()` and LangGraph nodes unchanged: Task 3 by omission.
- Verifies existing and new behavior: Task 4.

Known intentional gaps:

- Streaming article generation remains on Ark direct path.
- Prompt Registry and Config Center are not yet called by the financial project.
- Live shared-platform smoke testing requires both services running and seeded model policies.
