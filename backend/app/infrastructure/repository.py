"""通用异步 Repository 基类 —— CRUD + 分页 + 排序。"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.infrastructure.database import AsyncSessionLocal

T = TypeVar("T", bound=DeclarativeBase)


class BaseRepository(Generic[T]):
    """异步 CRUD 仓储基类。

    用法:
        class UserRepo(BaseRepository[User]):
            model = User
    """

    model: type[T]

    def __init__(self, db: AsyncSession | None = None):
        self._db: AsyncSession | None = db

    async def get_db(self) -> AsyncSession:
        if self._db:
            return self._db
        return AsyncSessionLocal()

    # ── 查询 ──────────────────────────────────────────

    async def get_by_id(self, id_: int) -> T | None:
        async with await self.get_db() as db:
            result = await db.execute(
                select(self.model).where(self.model.id == id_)
            )
            return result.scalar_one_or_none()

    async def get_or_404(self, id_: int) -> T:
        obj = await self.get_by_id(id_)
        if obj is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"{self.model.__name__} 不存在")
        return obj

    async def list_all(
        self,
        *filters: Any,
        order_by: Any | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[T], int]:
        """分页查询，返回 (数据列表, 总数)。"""
        async with await self.get_db() as db:
            q = select(self.model)
            count_q = select(func.count()).select_from(self.model)

            for f in filters:
                q = q.where(f)
                count_q = count_q.where(f)

            if order_by is not None:
                q = q.order_by(order_by)

            q = q.offset(offset).limit(min(limit, 200))

            result = await db.execute(q)
            rows = list(result.scalars().all())
            total = (await db.execute(count_q)).scalar() or 0

            return rows, total

    # ── 写入 ──────────────────────────────────────────

    async def create(self, **kwargs: Any) -> T:
        async with await self.get_db() as db:
            obj = self.model(**kwargs)
            db.add(obj)
            await db.commit()
            await db.refresh(obj)
            return obj

    async def update(self, id_: int, **kwargs: Any) -> T | None:
        async with await self.get_db() as db:
            obj = await self.get_by_id(id_)
            if obj is None:
                return None
            for key, value in kwargs.items():
                if hasattr(obj, key) and value is not None:
                    setattr(obj, key, value)
            await db.commit()
            await db.refresh(obj)
            return obj

    async def delete(self, id_: int) -> bool:
        async with await self.get_db() as db:
            result = await db.execute(
                delete(self.model).where(self.model.id == id_)
            )
            await db.commit()
            return result.rowcount > 0

    async def count(self, *filters: Any) -> int:
        async with await self.get_db() as db:
            q = select(func.count()).select_from(self.model)
            for f in filters:
                q = q.where(f)
            return (await db.execute(q)).scalar() or 0

    async def exists(self, *filters: Any) -> bool:
        return await self.count(*filters) > 0

    async def bulk_create(self, items: list[dict[str, Any]]) -> list[T]:
        async with await self.get_db() as db:
            objs = [self.model(**item) for item in items]
            db.add_all(objs)
            await db.commit()
            return objs
