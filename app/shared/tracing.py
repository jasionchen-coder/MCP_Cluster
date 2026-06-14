import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

TRACE_HEADER = "x-trace-id"


def new_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex}"


def get_trace_id(request: Request) -> str:
    trace_id = getattr(request.state, "trace_id", None)
    if trace_id:
        return trace_id
    return request.headers.get(TRACE_HEADER) or new_trace_id()


async def trace_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    trace_id = request.headers.get(TRACE_HEADER) or new_trace_id()
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers[TRACE_HEADER] = trace_id
    return response
