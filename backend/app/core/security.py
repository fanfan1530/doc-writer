"""
安全工具 — 输入清洗、速率限制。
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
    """简易基于内存的速率限制器（单进程，适用于开发/小规模部署）。"""

    def __init__(self):
        settings = get_settings()
        self._max_requests = settings.rate_limit_requests
        self._window = settings.rate_limit_window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self._window
        self._store[key] = [t for t in self._store[key] if t > window_start]
        if len(self._store[key]) >= self._max_requests:
            return False
        self._store[key].append(now)
        return True


rate_limiter = RateLimiter()
