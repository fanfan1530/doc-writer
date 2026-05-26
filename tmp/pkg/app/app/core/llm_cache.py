"""LLM 响应缓存 —— 基于 prompt + model + temperature 的哈希去重。"""

import hashlib
import json
import logging

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600  # 1 hour default


def _cache_key(prompt: str, model: str, temperature: float) -> str:
    """生成缓存键：SHA256(prompt | model | temperature)。"""
    payload = f"{prompt}|{model}|{temperature}"
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"llm:cache:{digest}"


async def get_cached(prompt: str, model: str, temperature: float) -> str | None:
    """从 Redis 获取缓存的 LLM 响应。"""
    try:
        from app.core.redis_client import get_redis, is_fake_redis
        redis = get_redis()
        if is_fake_redis():
            return None
        key = _cache_key(prompt, model, temperature)
        cached = await redis.get(key)
        if cached:
            logger.info("LLM 缓存命中: %s", key[:32])
            return cached
    except Exception:
        pass
    return None


async def set_cached(prompt: str, model: str, temperature: float, response: str) -> None:
    """缓存 LLM 响应到 Redis。"""
    try:
        from app.core.redis_client import get_redis, is_fake_redis
        redis = get_redis()
        if is_fake_redis():
            return
        key = _cache_key(prompt, model, temperature)
        await redis.setex(key, CACHE_TTL_SECONDS, response)
    except Exception:
        pass
