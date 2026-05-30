"""JWT 认证中间件 —— 验证 Bearer Token，将用户信息注入 request.state。"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.auth import decode_token
from app.core.security import get_user_permissions

PUBLIC_PATHS = {
    "/api/health",
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/refresh",
    "/docs",
    "/openapi.json",
    "/",
}


def _is_public(path: str) -> bool:
    if path in PUBLIC_PATHS or path.startswith("/assets/"):
        return True
    if path.startswith("/api/generation/templates"):
        return True
    # SPA fallback: non-API paths are frontend routes served by the catch-all
    if not path.startswith("/api/") and path not in ("/docs", "/openapi.json"):
        return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if _is_public(request.url.path) or request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": True, "code": "UNAUTHORIZED", "message": "缺少认证令牌"},
            )

        try:
            payload = decode_token(auth_header[7:])
        except HTTPException:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": True, "code": "UNAUTHORIZED", "message": "无效的认证令牌"},
            )

        role = payload.get("role", "user")
        request.state.user_id = payload.get("user_id", 0)
        request.state.username = payload.get("sub", "")
        request.state.role = role
        request.state.permissions = get_user_permissions(role)

        return await call_next(request)
