"""异步 SQLAlchemy 数据库引擎 —— 本地开发使用 SQLite，生产使用 PostgreSQL。

环境变量:
    DATABASE_URL — 完整数据库连接字符串
        SQLite 开发: sqlite+aiosqlite:///path/to/data.db
        PostgreSQL 生产: postgresql+asyncpg://user:pass@host:5432/dbname
    DB_POOL_SIZE — 连接池大小（默认 5，仅 PostgreSQL 生效）
    DB_MAX_OVERFLOW — 连接池溢出上限（默认 10）
"""

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_DEFAULT_SQLITE = "sqlite+aiosqlite:///" + str(
    Path(__file__).resolve().parent.parent / "knowledge" / "data.db"
)

DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_SQLITE)
_IS_POSTGRES = DATABASE_URL.startswith("postgresql")

_engine_kwargs: dict = {"echo": False}
if _IS_POSTGRES:
    _engine_kwargs.update({
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    })

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """创建所有表（首次启动时调用）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """FastAPI 依赖注入：获取异步数据库会话。"""
    async with AsyncSessionLocal() as session:
        yield session
