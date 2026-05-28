"""通知服务 —— 通知创建 + WebSocket 广播 + 事件触发钩子。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.models import Notification

logger = logging.getLogger(__name__)

# 已连接的 WebSocket 客户端: {user_id: set[WebSocket]}
_ws_clients: dict[int, set[Any]] = {}


# ── WebSocket 连接管理 ───────────────────────────────────

def ws_connect(user_id: int, ws: Any) -> None:
    _ws_clients.setdefault(user_id, set()).add(ws)


def ws_disconnect(user_id: int, ws: Any) -> None:
    if user_id in _ws_clients:
        _ws_clients[user_id].discard(ws)
        if not _ws_clients[user_id]:
            del _ws_clients[user_id]


async def ws_broadcast(user_id: int, data: dict) -> None:
    """向指定用户的所有 WebSocket 连接推送消息。"""
    clients = _ws_clients.get(user_id, set())
    if not clients:
        return
    payload = json.dumps(data, ensure_ascii=False)
    dead: list[Any] = []
    for ws in clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)
    if not clients and user_id in _ws_clients:
        del _ws_clients[user_id]


# ── 通知服务 ────────────────────────────────────────────

NOTIFICATION_TYPES = {
    "CASE_ASSIGNED": "案件分配",
    "DOCUMENT_SUBMITTED": "文书提交审核",
    "DOCUMENT_APPROVED": "文书审批通过",
    "DOCUMENT_REJECTED": "文书被退回",
    "DEADLINE_WARNING": "截止日期预警",
    "SYSTEM_ANNOUNCEMENT": "系统公告",
}


class NotificationService:

    async def create(
        self, user_id: int, ntype: str, title: str, content: str = "",
        related_case_id: int | None = None,
    ) -> dict:
        """创建通知并实时推送。"""
        async with AsyncSessionLocal() as db:
            notif = Notification(
                user_id=user_id,
                type=ntype,
                title=title,
                content=content,
                related_case_id=related_case_id,
            )
            db.add(notif)
            await db.commit()
            await db.refresh(notif)

        data = {
            "id": notif.id,
            "type": notif.type,
            "title": notif.title,
            "content": notif.content,
            "related_case_id": notif.related_case_id,
            "is_read": notif.is_read,
            "created_at": notif.created_at.isoformat() if notif.created_at else "",
        }

        # 异步推送（不阻塞创建流程）
        asyncio.create_task(ws_broadcast(user_id, data))

        return data

    async def get_unread_count(self, user_id: int) -> int:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func
            return (await db.execute(
                select(func.count()).select_from(Notification).where(
                    Notification.user_id == user_id,
                    Notification.is_read == False,  # noqa: E712
                ),
            )).scalar() or 0

    async def list_notifications(
        self, user_id: int, limit: int = 20, offset: int = 0,
        ntype: str | None = None,
    ) -> tuple[list[dict], int]:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func, desc

            q = select(Notification).where(Notification.user_id == user_id)
            count_q = select(func.count()).select_from(Notification).where(
                Notification.user_id == user_id,
            )

            if ntype:
                q = q.where(Notification.type == ntype)
                count_q = count_q.where(Notification.type == ntype)

            total = (await db.execute(count_q)).scalar() or 0
            result = await db.execute(
                q.order_by(desc(Notification.created_at)).offset(offset).limit(min(limit, 100)),
            )
            rows = result.scalars().all()
            return [
                {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "content": n.content,
                    "related_case_id": n.related_case_id,
                    "is_read": n.is_read,
                    "created_at": n.created_at.isoformat() if n.created_at else "",
                }
                for n in rows
            ], total

    async def mark_read(self, notif_id: int, user_id: int) -> bool:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            n = (await db.execute(
                select(Notification).where(
                    Notification.id == notif_id,
                    Notification.user_id == user_id,
                ),
            )).scalar_one_or_none()
            if not n:
                return False
            n.is_read = True
            await db.commit()
            return True

    async def mark_all_read(self, user_id: int) -> int:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, update
            result = await db.execute(
                update(Notification)
                .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
                .values(is_read=True)
            )
            await db.commit()
            return result.rowcount


notification_service = NotificationService()
