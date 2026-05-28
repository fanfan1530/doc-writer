"""集中配置管理 —— 所有环境变量通过 pydantic-settings 加载。"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # ── 应用 ──────────────────────────────────────────
    app_name: str = "智慧警务智能工作台"
    app_version: str = "2.1.0"
    debug: bool = False

    # ── 数据库 ────────────────────────────────────────
    # SQLite 开发: sqlite+aiosqlite:///path/to/data.db
    # PostgreSQL 生产: postgresql+asyncpg://user:pass@host:5432/dbname
    database_url: str = ""
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # ── Redis (可选) ──────────────────────────────────
    redis_url: str = ""

    # ── LLM ───────────────────────────────────────────
    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model_large: str = "qwen2.5:72b"
    llm_model_small: str = "qwen2.5:7b"
    llm_max_input_chars: int = 16000

    # ── 知识库 ────────────────────────────────────────
    knowledge_dir: str = "./app/knowledge"
    chroma_persist_dir: str = ""

    # ── 速率限制 ──────────────────────────────────────
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60

    # ── CORS ──────────────────────────────────────────
    allowed_origins: list[str] = ["http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:5178"]

    # ── JWT ───────────────────────────────────────────
    jwt_secret_key: str = "doc-writer-dev-secret-change-in-production"
    jwt_expire_minutes: int = 480
    jwt_refresh_days: int = 7

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()

