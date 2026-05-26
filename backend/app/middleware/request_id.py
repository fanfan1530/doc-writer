"""Request ID middleware — 为每个请求生成唯一 ID，贯穿整个请求生命周期。"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

HEADER_NAME = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """将 X-Request-ID 注入请求上下文和响应头。"""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get(HEADER_NAME) or uuid.uuid4().hex[:12]
        request_id_ctx.set(rid)
        request.state.request_id = rid
        response: Response = await call_next(request)
        response.headers[HEADER_NAME] = rid
        return response


def get_request_id() -> str:
    """获取当前请求的 request_id（可在任何地方调用）。"""
    return request_id_ctx.get()
