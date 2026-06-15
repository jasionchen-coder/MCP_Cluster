from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.modules.config_center.router import router as config_center_router
from app.modules.llm_gateway.router import router as llm_gateway_router
from app.modules.prompt_registry.router import router as prompt_registry_router
from app.modules.rag_service.router import router as rag_service_router
from app.modules.secret_manager.router import router as secret_manager_router
from app.modules.tool_registry.router import router as tool_registry_router
from app.shared.config import get_settings
from app.shared.database import init_db
from app.shared.errors import APIError, api_error_handler, http_error_handler
from app.shared.tracing import get_trace_id, trace_middleware

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(trace_middleware)
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.include_router(config_center_router)
app.include_router(llm_gateway_router)
app.include_router(prompt_registry_router)
app.include_router(rag_service_router)
app.include_router(secret_manager_router)
app.include_router(tool_registry_router)


@app.get("/healthz")
async def healthz(request: Request) -> dict[str, str]:
    return {"status": "ok", "trace_id": get_trace_id(request)}
