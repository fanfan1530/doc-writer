"""
安全工具 — 输入清洗、速率限制。
Redis 模式下使用滑动窗口算法，无 Redis 时回退到内存限流。
"""
import re
import time
from collections import defaultdict

from app.config import get_settings


def sanitize_llm_input(text: str) -> str:
    """清洗用户输入，防止 prompt 注入。"""
    settings = get_settings()
    if not text:
        return ""
    text = text[:settings.llm_max_input_chars]
    text = text.replace("```", "'''")
    text = re.sub(r"(<\|.*?\|>)", r"[BLOCKED:\1]", text)
    return text


class RateLimiter:
    """速率限制器 —— Redis 滑动窗口优先，内存回退。"""

    def __init__(self):
        settings = get_settings()
        self._max_requests = settings.rate_limit_requests
        self._window = settings.rate_limit_window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)
        self._redis = None
        self._redis_checked = False

    async def is_allowed(self, key: str) -> bool:
        # 尝试 Redis
        redis = self._get_redis()
        if redis:
            return await self._redis_check(redis, key)
        # 内存回退
        return self._memory_check(key)

    def is_allowed_sync(self, key: str) -> bool:
        """同步版本 —— 仅使用内存限流。"""
        return self._memory_check(key)

    def _get_redis(self):
        if not self._redis_checked:
            try:
                from app.core.redis_client import get_redis, is_fake_redis
                r = get_redis()
                # fakeredis 不支持滑动窗口脚本，使用内存回退
                if not is_fake_redis():
                    self._redis = r
            except Exception:
                pass
            self._redis_checked = True
        return self._redis

    async def _redis_check(self, redis, key: str) -> bool:
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
                return count < self._max_requests
        except Exception:
            return self._memory_check(key)

    def _memory_check(self, key: str) -> bool:
        now = time.time()
        window_start = now - self._window
        self._store[key] = [t for t in self._store[key] if t > window_start]
        if len(self._store[key]) >= self._max_requests:
            return False
        self._store[key].append(now)
        return True


rate_limiter = RateLimiter()
