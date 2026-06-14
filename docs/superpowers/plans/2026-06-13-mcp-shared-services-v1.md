# MCP 共享服务 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `D:\Code\MCP_Cluster` 中实现第一版模块化单体 FastAPI 共享 AI 服务平台。

**Architecture:** 使用一个 FastAPI 应用承载 Config Center、Prompt Registry、LLM Gateway 和 RAG Service。模块之间通过显式 service 函数和数据库模型协作，外部统一通过 HTTP API 调用。

**Tech Stack:** Python 3.11+、uv、FastAPI、Pydantic v2、SQLAlchemy 2 async、Alembic、httpx、pytest、pytest-asyncio、aiosqlite。

---

### Task 1: 项目骨架与基础测试

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `README.md`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/shared/config.py`
- Create: `app/shared/tracing.py`
- Create: `app/shared/errors.py`
- Create: `tests/conftest.py`
- Create: `tests/test_health_and_errors.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_health_and_errors.py` with tests for `/healthz`, trace ID propagation, and unified 404 errors.

- [ ] **Step 2: Run tests and verify RED**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_health_and_errors.py -v`

Expected: fail because `app.main` does not exist.

- [ ] **Step 3: Implement minimal FastAPI app**

Create project metadata, settings, tracing middleware, unified API exception handler, and `/healthz`.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_health_and_errors.py -v`

Expected: pass.

### Task 2: Async Database Foundation

**Files:**
- Create: `app/shared/database.py`
- Create: `app/shared/models.py`
- Modify: `app/main.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_database.py` to verify app startup creates tables against a temporary SQLite database.

- [ ] **Step 2: Run tests and verify RED**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_database.py -v`

Expected: fail because database helpers do not exist.

- [ ] **Step 3: Implement database session and startup initialization**

Use SQLAlchemy async engine, `async_sessionmaker`, declarative base, and `init_db()`.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_database.py tests/test_health_and_errors.py -v`

Expected: pass.

### Task 3: Config Center

**Files:**
- Create: `app/modules/config_center/__init__.py`
- Create: `app/modules/config_center/models.py`
- Create: `app/modules/config_center/schemas.py`
- Create: `app/modules/config_center/service.py`
- Create: `app/modules/config_center/router.py`
- Modify: `app/main.py`
- Test: `tests/test_config_center.py`

- [ ] **Step 1: Write failing tests**

Create tests for creating/updating a task config, reading it by `project_id/env/task_type`, and listing change logs.

- [ ] **Step 2: Run tests and verify RED**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_config_center.py -v`

Expected: fail because config routes do not exist.

- [ ] **Step 3: Implement Config Center models, service, and routes**

Implement `config_task_configs` and `config_change_logs` with project/env/task uniqueness and change log recording.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_config_center.py -v`

Expected: pass.

### Task 4: Prompt Registry

**Files:**
- Create: `app/modules/prompt_registry/__init__.py`
- Create: `app/modules/prompt_registry/models.py`
- Create: `app/modules/prompt_registry/schemas.py`
- Create: `app/modules/prompt_registry/service.py`
- Create: `app/modules/prompt_registry/router.py`
- Modify: `app/main.py`
- Test: `tests/test_prompt_registry.py`

- [ ] **Step 1: Write failing tests**

Create tests for prompt creation, version creation, publish, render, render log, and missing required variable error.

- [ ] **Step 2: Run tests and verify RED**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_prompt_registry.py -v`

Expected: fail because prompt routes do not exist.

- [ ] **Step 3: Implement Prompt Registry**

Implement `{{variable}}` rendering, JSON-schema required field validation, published-version enforcement for default production render, and render logs.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_prompt_registry.py -v`

Expected: pass.

### Task 5: LLM Gateway

**Files:**
- Create: `app/modules/llm_gateway/__init__.py`
- Create: `app/modules/llm_gateway/models.py`
- Create: `app/modules/llm_gateway/schemas.py`
- Create: `app/modules/llm_gateway/provider.py`
- Create: `app/modules/llm_gateway/service.py`
- Create: `app/modules/llm_gateway/router.py`
- Modify: `app/main.py`
- Test: `tests/test_llm_gateway.py`

- [ ] **Step 1: Write failing tests**

Create tests for provider/policy setup, `/api/v1/llm/generate`, `/api/v1/llm/json-generate`, invocation logs, missing policy error, and `/v1/chat/completions` compatibility.

- [ ] **Step 2: Run tests and verify RED**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_llm_gateway.py -v`

Expected: fail because LLM routes do not exist.

- [ ] **Step 3: Implement LLM Gateway with injectable provider**

Use a provider abstraction. Unit tests inject a fake provider; production provider uses `httpx` against OpenAI-compatible chat completions.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_llm_gateway.py -v`

Expected: pass.

### Task 6: RAG Service V1

**Files:**
- Create: `app/modules/rag_service/__init__.py`
- Create: `app/modules/rag_service/models.py`
- Create: `app/modules/rag_service/schemas.py`
- Create: `app/modules/rag_service/service.py`
- Create: `app/modules/rag_service/router.py`
- Modify: `app/main.py`
- Test: `tests/test_rag_service.py`

- [ ] **Step 1: Write failing tests**

Create tests for knowledge base creation, document ingestion, deterministic chunking, same-project search, evidence pack creation, and cross-project access denial.

- [ ] **Step 2: Run tests and verify RED**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_rag_service.py -v`

Expected: fail because RAG routes do not exist.

- [ ] **Step 3: Implement RAG V1**

Implement metadata tables, fixed-size text chunking, lexical chunk search constrained by `project_id + env + kb_ids`, retrieval logs, and evidence packs.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `uv --cache-dir .uv-cache run python -m pytest tests/test_rag_service.py -v`

Expected: pass.

### Task 7: Seed Scripts And Final Verification

**Files:**
- Create: `scripts/seed_dev_data.py`
- Create: `scripts/smoke_test.py`
- Modify: `README.md`
- Test: all tests

- [ ] **Step 1: Write failing tests**

Add tests that verify seeded config and prompt values can be loaded through service functions.

- [ ] **Step 2: Run tests and verify RED**

Run: `uv --cache-dir .uv-cache run python -m pytest -v`

Expected: fail because seed helpers do not exist.

- [ ] **Step 3: Implement seed and smoke scripts**

Seed `finance_media/dev/generate_article`, `aigc_rtc/dev/voice_dialogue`, and `finance.article.draft`.

- [ ] **Step 4: Run full verification**

Run: `uv --cache-dir .uv-cache run python -m pytest -v`

Expected: all tests pass.

Run: `uv --cache-dir .uv-cache run python -m compileall app scripts`

Expected: compile succeeds.

---

## Self-Review

Spec coverage:

- Project skeleton and `/healthz`: Task 1.
- Async storage and migration-ready DB foundation: Task 2.
- Config Center: Task 3.
- Prompt Registry: Task 4.
- LLM Gateway and OpenAI-compatible route: Task 5.
- RAG API, metadata, isolation, and evidence packs: Task 6.
- Seed data and final verification: Task 7.

Known intentional gaps:

- Real vector backend is deferred by the approved design.
- Full edits inside the two existing projects are deferred by the approved design.
- Git commits are not included because `D:\Code\MCP_Cluster` is not currently a git repository.
