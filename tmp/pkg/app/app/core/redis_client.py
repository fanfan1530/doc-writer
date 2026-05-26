"""Redis 客户端 —— 统一管理连接，本地开发可回退到 fakeredis。"""

import os
import logging

logger = logging.getLogger(__name__)

_redis = None
_use_fake = False


def get_redis():
    global _redis, _use_fake
    if _redis is not None:
        return _redis

    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        try:
            import redis.asyncio as aioredis
            _redis = aioredis.from_url(redis_url, decode_responses=True)
            _use_fake = False
            logger.info("Redis 连接已建立: %s", redis_url)
            return _redis
        except Exception:
            logger.warning("Redis 连接失败，回退到本地内存存储")

    import fakeredis.aioredis
    _redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    _use_fake = True
    logger.info("使用 fakeredis 内存存储")
    return _redis


def is_fake_redis() -> bool:
    return _use_fake
