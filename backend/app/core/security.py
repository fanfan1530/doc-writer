"""
安全工具 — 输入清洗、速率限制。
Redis 模式下使用滑动窗口算法，无 Redis 时回退到内存限流。
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings


def sanitize_llm_input(text: str) -> str:
    """清洗用户输入，防止 prompt 注入和恶意字符。"""
    settings = get_settings()
    if not text:
        return ""
    text = text[:settings.llm_max_input_chars]
    # 移除 null 字节和 Unicode 控制字符（保留常用换行/制表）
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    # 移除 Unicode 双向文本覆盖字符（防止 bidi 攻击）
    text = re.sub(r'[‪-‮⁦-⁩]', '', text)
    # 防止 prompt 注入特殊标记
    text = text.replace("```", "'''")
    text = re.sub(r"(<\|.*?\|>)", r"[BLOCKED:\1]", text)
    # 阻止常见的 prompt 注入角色扮演模式
    text = re.sub(r'(?i)(ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?))',
                  r'[BLOCKED]', text)
    return text


@dataclass
class RateLimitInfo:
    allowed: bool = True
    remaining: int = 0
    limit: int = 0
    reset_at: float = 0.0


class RateLimiter:
    """速率限制器 —— Redis 滑动窗口优先，内存回退。

    使用 check() 代替 is_allowed() 可获取标准限流头信息。
    """

    def __init__(self):
        settings = get_settings()
        self._max_requests = settings.rate_limit_requests
        self._window = settings.rate_limit_window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)
        self._redis = None
        self._redis_checked = False

    async def check(self, key: str) -> RateLimitInfo:
        redis = self._get_redis()
        if redis:
            return await self._redis_check(redis, key)
        return self._memory_check(key)

    async def is_allowed(self, key: str) -> bool:
        return (await self.check(key)).allowed

    def is_allowed_sync(self, key: str) -> bool:
        return self._memory_check(key).allowed

    def _get_redis(self):
        if not self._redis_checked:
            try:
                from app.core.redis_client import get_redis, is_fake_redis
                r = get_redis()
                if not is_fake_redis():
                    self._redis = r
            except Exception:
                pass
            self._redis_checked = True
        return self._redis

    async def _redis_check(self, redis, key: str) -> RateLimitInfo:
        now = time.time()
        window_start = now - self._window
        rkey = f"ratelimit:{key}"
        try:
            async with redis.pipeline() as pipe:
                await pipe.zremrangebyscore(rkey, 0, window_start)
                await pipe.zcard(rkey)
                await pipe.zadd(rkey, {str(now): now})
                await pipe.expire(rkey, self._window + 1)
                _, count, _, _ = await pipe.execute()
            remaining = max(0, self._max_requests - count)
            oldest = now
            try:
                oldest = float(await redis.zrange(rkey, 0, 0, withscores=True)[0][1])
            except Exception:
                pass
            return RateLimitInfo(
                allowed=count < self._max_requests,
                remaining=remaining,
                limit=self._max_requests,
                reset_at=oldest + self._window,
            )
        except Exception:
            return self._memory_check(key)

    def _memory_check(self, key: str) -> RateLimitInfo:
        now = time.time()
        window_start = now - self._window
        self._store[key] = [t for t in self._store[key] if t > window_start]
        current = len(self._store[key])
        remaining = max(0, self._max_requests - current)
        reset_at = (self._store[key][0] + self._window) if self._store[key] else now + self._window
        if current >= self._max_requests:
            return RateLimitInfo(allowed=False, remaining=0, limit=self._max_requests, reset_at=reset_at)
        self._store[key].append(now)
        return RateLimitInfo(allowed=True, remaining=remaining, limit=self._max_requests, reset_at=reset_at)


def rate_limit_headers(info: RateLimitInfo) -> dict[str, str]:
    """生成标准限流响应头（IETF 草案格式）。"""
    return {
        "X-RateLimit-Limit": str(info.limit),
        "X-RateLimit-Remaining": str(info.remaining),
        "X-RateLimit-Reset": str(int(info.reset_at)),
    }


def raise_rate_limited(info: RateLimitInfo) -> None:
    """抛出带标准限流头的 429 响应。"""
    retry_after = max(1, int(info.reset_at - time.time()))
    raise HTTPException(
        status_code=429,
        detail=f"请求过于频繁，请在 {retry_after} 秒后重试",
        headers={
            "Retry-After": str(retry_after),
            **rate_limit_headers(info),
        },
    )


rate_limiter = RateLimiter()


# ── 权限控制 ──────────────────────────────────────────────

from typing import Callable
from fastapi import Request, HTTPException, status

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "system_admin": [
        "users:read", "users:write", "roles:read", "roles:write",
        "audit:read", "cases:read", "cases:write", "cases:delete",
        "documents:read", "documents:write", "documents:approve", "documents:reject",
        "models:read", "models:write", "knowledge:read", "knowledge:write",
        "analytics:read", "copilot:use",
    ],
    "unit_leader": [
        "cases:read", "documents:read", "documents:approve", "documents:reject",
        "analytics:read", "copilot:use", "knowledge:read",
    ],
    "case_officer": [
        "cases:read", "cases:write", "documents:read", "documents:write",
        "copilot:use", "knowledge:read",
    ],
    "reviewer": [
        "cases:read", "documents:read", "documents:approve", "documents:reject",
        "copilot:use", "knowledge:read",
    ],
    "auditor": [
        "cases:read", "documents:read", "audit:read", "analytics:read", "knowledge:read",
    ],
    "user": [
        "cases:read", "documents:read", "documents:write", "copilot:use", "knowledge:read",
    ],
}

ROLE_LABELS: dict[str, str] = {
    "system_admin": "系统管理员",
    "unit_leader": "单位领导",
    "case_officer": "办案民警",
    "reviewer": "法制员",
    "auditor": "督察审计",
    "user": "普通用户",
}

ALL_ROLES = list(ROLE_LABELS.keys())


def get_user_permissions(role: str) -> list[str]:
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS.get("user", []))


def require_permission(permission: str) -> Callable:
    """FastAPI 依赖注入：检查当前用户是否拥有指定权限。"""

    async def checker(request: Request) -> None:
        role = getattr(request.state, "role", "user")
        allowed = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["user"])
        if permission not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要 {permission}",
            )

    return checker
