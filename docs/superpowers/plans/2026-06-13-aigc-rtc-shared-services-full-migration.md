# 智能客服共享服务完整迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将智能客服的 Config、Prompt、RAG 和 LLM 调度接入 MCP_Cluster，并让知识库数据落在本地 PostgreSQL。

**Architecture:** MCP_Cluster 作为共享服务平台，提供配置、Prompt、RAG 和模型调度；LLMServer 保持外部 OpenAI-compatible 接口与本地会话历史。开启共享平台后，LLMServer 通过 HTTP client 读取配置、渲染 Prompt、检索 RAG，再调用 LLM Gateway。

**Tech Stack:** FastAPI, SQLAlchemy async, PostgreSQL via `postgresql+asyncpg`, httpx, unittest/pytest。

---

### Task 1: MCP_Cluster Seed

**Files:**
- Modify: `scripts/seed_dev_data.py`
- Modify: `.env.example`
- Test: `tests/test_seed_dev_data.py`

- [ ] 写失败测试：断言 `aigc_rtc/dev/voice_dialogue` 开启 RAG，`rag_policy_id=aigc_voice_kb`，三个智能客服 prompt 可渲染，`aigc_voice_kb` 可检索。
- [ ] 运行 `uv --cache-dir .uv-cache run python -m pytest tests/test_seed_dev_data.py -v`，预期失败。
- [ ] 修改 seed：创建智能客服 KB、文档和三个 Prompt，更新 config。
- [ ] 运行同一测试，预期通过。

### Task 2: LLMServer Shared Clients

**Files:**
- Modify: `D:\Code\LangChain\LLMServer\llm\shared_platform_client.py`
- Test: `D:\Code\LangChain\LLMServer\tests\test_shared_platform_migration.py`

- [ ] 写失败测试：配置中心返回的 `model_policy_id` 会覆盖静态 env；RAG search 返回会归一化为 `{text, score, source}`；Prompt render 返回文本。
- [ ] 用 `D:\Anaconda3\envs\langchain\python.exe -m unittest discover -s tests -v` 验证失败。
- [ ] 扩展 shared client：`get_task_config()`、`render_prompt()`、`search_rag()`、`resolve_model_policy_id()`。
- [ ] 运行测试，预期通过。

### Task 3: LLMServer Prompt/RAG Pipeline

**Files:**
- Modify: `D:\Code\LangChain\LLMServer\rag\pipeline.py`
- Modify: `D:\Code\LangChain\LLMServer\rag\prompt.py`
- Modify: `D:\Code\LangChain\LLMServer\llm\router.py`
- Test: `D:\Code\LangChain\LLMServer\tests\test_shared_pipeline.py`

- [ ] 写失败测试：开启共享平台时 `build_messages()` 使用 shared RAG 和 shared Prompt；session 创建使用 shared base prompt；关闭开关时仍走本地逻辑。
- [ ] 运行测试，预期失败。
- [ ] 实现 shared 分支和 fallback 分支。
- [ ] 运行测试，预期通过。

### Task 4: Verification

**Files:**
- No production file edits.

- [ ] MCP_Cluster: `uv --cache-dir .uv-cache run python -m pytest -v`
- [ ] MCP_Cluster: `uv --cache-dir .uv-cache run python -m compileall app scripts`
- [ ] LLMServer: `$env:PYTHONPYCACHEPREFIX='D:\Code\MCP_Cluster\.pycache-langchain'; D:\Anaconda3\envs\langchain\python.exe -m unittest discover -s tests -v`
- [ ] LLMServer: `$env:PYTHONPYCACHEPREFIX='D:\Code\MCP_Cluster\.pycache-langchain'; D:\Anaconda3\envs\langchain\python.exe -m compileall llm rag config.py`

