"""异步 SQLAlchemy 数据库引擎 —— 本地开发使用 aiosqlite，生产使用 PostgreSQL。"""

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///" + str(
        Path(__file__).resolve().parent.parent / "knowledge" / "data.db"
    ),
)

engine = create_async_engine(DATABASE_URL, echo=False)
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
