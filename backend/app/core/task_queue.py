"""ARQ 异步任务队列 —— 用于长时间 LLM 调用。本地无 Redis 时回退到直接调用。"""

import os
import logging

from arq import create_pool
from arq.connections import RedisSettings

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "")
_pool = None


async def get_pool():
    global _pool
    if _pool is not None:
        return _pool
    if not REDIS_URL:
        return None
    try:
        _pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        logger.info("ARQ 任务队列已连接")
        return _pool
    except Exception:
        logger.warning("ARQ 连接失败，任务将同步执行")
        return None


async def enqueue_task(task_name: str, **kwargs) -> str | None:
    """将任务加入队列，返回 job_id；队列不可用时返回 None。"""
    pool = await get_pool()
    if pool is None:
        return None
    job = await pool.enqueue_job(task_name, **kwargs)
    return job.job_id


async def get_job_status(job_id: str) -> dict:
    """查询任务状态。"""
    pool = await get_pool()
    if pool is None:
        return {"status": "unknown", "message": "任务队列未启用"}
    job = await pool.get_job(job_id)
    if job is None:
        return {"status": "not_found"}
    return {
        "status": "complete" if job.result is not None else "pending",
        "result": job.result if job.result is not None else None,
    }
