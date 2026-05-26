"""全局异常处理 —— 统一的 JSON 错误响应格式。"""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.middleware.request_id import get_request_id

logger = logging.getLogger("app.errors")


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    rid = get_request_id()
    logger.warning(
        "HTTP %d: %s [rid=%s] [path=%s]",
        exc.status_code, exc.detail, rid, request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": f"HTTP_{exc.status_code}",
            "message": str(exc.detail),
            "request_id": rid,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    rid = get_request_id()
    errors = []
    for e in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in e["loc"]),
            "message": e["msg"],
            "type": e["type"],
        })
    logger.warning(
        "Validation error [rid=%s] [path=%s]: %s",
        rid, request.url.path, errors,
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "code": "VALIDATION_ERROR",
            "message": "请求参数校验失败",
            "request_id": rid,
            "detail": errors,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = get_request_id()
    logger.exception(
        "Unhandled error [rid=%s] [path=%s]: %s",
        rid, request.url.path, str(exc)[:300],
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误" if not __debug__ else str(exc)[:300],
            "request_id": rid,
        },
    )
