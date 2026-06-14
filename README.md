# MCP Shared Services

模块化单体 FastAPI 共享 AI 服务平台。

## 本地开发

```powershell
uv --cache-dir .uv-cache sync --extra dev --no-managed-python --python D:\sorftWare_package\anaconda\python.exe
uv --cache-dir .uv-cache run python -m pytest -v
uv --cache-dir .uv-cache run uvicorn app.main:app --reload
```

初始化开发数据：

```powershell
uv --cache-dir .uv-cache run python -m scripts.seed_dev_data
```

冒烟检查：

```powershell
uv --cache-dir .uv-cache run python -m scripts.smoke_test
```

## 当前范围

- Config Center
- Prompt Registry
- LLM Gateway
- RAG Service V1
