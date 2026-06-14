from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.tracing import get_trace_id


class APIError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail={
                "code": code,
                "message": message,
                "details": details or {},
            },
        )


def error_payload(code: str, message: str, details: dict[str, Any], trace_id: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "trace_id": trace_id,
    }


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code=detail.get("code", "INTERNAL_ERROR"),
            message=detail.get("message", "Internal error"),
            details=detail.get("details", {}),
            trace_id=get_trace_id(request),
        ),
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content=error_payload(
                code="NOT_FOUND",
                message="Resource not found",
                details={"path": request.url.path},
                trace_id=get_trace_id(request),
            ),
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code="HTTP_ERROR",
            message=str(exc.detail),
            details={},
            trace_id=get_trace_id(request),
        ),
    )
