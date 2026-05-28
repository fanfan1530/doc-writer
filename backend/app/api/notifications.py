"""通知 API —— 分页查询 + 标记已读。"""

from fastapi import APIRouter, HTTPException, Request, status, Query
from app.services.notification_service import notification_service

router = APIRouter(prefix="/api/notifications", tags=["通知"])


@router.get("")
async def list_notifications(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    type: str | None = Query(None, alias="type"),
):
    """分页获取当前用户的通知列表。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    items, total = await notification_service.list_notifications(
        user_id, limit=limit, offset=offset, ntype=type,
    )
    return {"notifications": items, "total": total}


@router.get("/unread-count")
async def unread_count(request: Request):
    """获取当前用户未读通知数。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    count = await notification_service.get_unread_count(user_id)
    return {"count": count}


@router.put("/{notif_id}/read")
async def mark_read(notif_id: int, request: Request):
    """标记单条通知为已读。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    ok = await notification_service.mark_read(notif_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"status": "ok"}


@router.post("/mark-all-read")
async def mark_all_read(request: Request):
    """标记所有通知为已读。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    count = await notification_service.mark_all_read(user_id)
    return {"status": "ok", "count": count}
