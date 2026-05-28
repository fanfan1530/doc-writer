"""Request timing middleware — 结构化访问日志 + X-Process-Time 头。"""

import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.request_id import get_request_id

logger = logging.getLogger("app.access")
EXCLUDED_PATHS = {"/api/health", "/metrics", "/docs", "/openapi.json"}


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """记录每个请求的方法、路径、状态码、耗时，并添加 X-Process-Time 头。"""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        start = time.monotonic()
        response: Response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        response.headers["X-Process-Time"] = f"{duration_ms:.1f}"

        rid = get_request_id()
        client_ip = request.client.host if request.client else "-"
        ua = request.headers.get("user-agent", "-")[:120]

        logger.info(
            '{"method": "%s", "path": "%s", "status": %d, "duration_ms": %.1f, '
            '"client_ip": "%s", "request_id": "%s", "user_agent": "%s"}',
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            client_ip,
            rid,
            ua,
        )
        return response
