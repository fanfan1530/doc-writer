"""管理 API —— 用户角色管理 + 审计日志查询。"""

from fastapi import APIRouter, HTTPException, Request, status, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc

from app.core.security import (
    require_permission, get_user_permissions, ROLE_LABELS, ALL_ROLES,
)
from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.models import User, AuditLog

router = APIRouter(prefix="/api/admin", tags=["系统管理"])


# ── 请求模型 ─────────────────────────────────────────────

class UpdateRoleRequest(BaseModel):
    role: str = Field(..., description="角色标识")


class UpdateStatusRequest(BaseModel):
    is_active: bool = Field(...)


class UpdateUserRequest(BaseModel):
    display_name: str = Field("", max_length=64)
    unit: str = Field("", max_length=128)
    role: str = Field("", max_length=32)


# ── 用户管理 ─────────────────────────────────────────────

@router.get("/users")
async def list_users(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _=Depends(require_permission("users:read")),
):
    """分页获取用户列表（需 users:read 权限）。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
        )
        rows = result.scalars().all()
        total = (await db.execute(select(func.count()).select_from(User))).scalar()

        return {
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "display_name": u.display_name or u.username,
                    "unit": u.unit or "",
                    "role": u.role,
                    "role_label": ROLE_LABELS.get(u.role, "未知"),
                    "permissions": get_user_permissions(u.role),
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat() if u.created_at else "",
                }
                for u in rows
            ],
            "total": total,
            "roles": [{"key": k, "label": v} for k, v in ROLE_LABELS.items()],
        }


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    request: Request,
    _=Depends(require_permission("users:write")),
):
    """更新用户信息（角色、显示名、单位）。"""
    if body.role and body.role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail=f"无效角色: {body.role}")

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        if body.role:
            user.role = body.role
        if body.display_name:
            user.display_name = body.display_name
        if body.unit:
            user.unit = body.unit

        # 记录审计日志
        current_user = getattr(request.state, "username", "unknown")
        db.add(AuditLog(
            user_id=getattr(request.state, "user_id", 0),
            username=current_user,
            action="user_update",
            resource_type="user",
            resource_id=str(user_id),
            detail={
                "role": body.role,
                "display_name": body.display_name,
                "unit": body.unit,
            },
            ip_address=request.client.host if request.client else "",
        ))
        await db.commit()

        return {
            "status": "ok",
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "role_label": ROLE_LABELS.get(user.role, "未知"),
                "permissions": get_user_permissions(user.role),
                "is_active": user.is_active,
            },
        }


@router.put("/users/{user_id}/status")
async def toggle_user_status(
    user_id: int,
    body: UpdateStatusRequest,
    request: Request,
    _=Depends(require_permission("users:write")),
):
    """启用/禁用用户。"""
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        current_user_id = getattr(request.state, "user_id", 0)
        if user.id == current_user_id:
            raise HTTPException(status_code=400, detail="不能禁用自己")

        user.is_active = body.is_active

        action = "user_enable" if body.is_active else "user_disable"
        db.add(AuditLog(
            user_id=current_user_id,
            username=getattr(request.state, "username", "unknown"),
            action=action,
            resource_type="user",
            resource_id=str(user_id),
            detail={"is_active": body.is_active},
            ip_address=request.client.host if request.client else "",
        ))
        await db.commit()
        return {"status": "ok", "is_active": user.is_active}


# ── 审计日志 ─────────────────────────────────────────────

@router.get("/audit")
async def list_audit_logs(
    request: Request,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    _=Depends(require_permission("audit:read")),
):
    """分页查询审计日志（需 audit:read 权限）。"""
    async with AsyncSessionLocal() as db:
        q = select(AuditLog)
        count_q = select(func.count()).select_from(AuditLog)

        if user_id:
            q = q.where(AuditLog.user_id == user_id)
            count_q = count_q.where(AuditLog.user_id == user_id)
        if action:
            q = q.where(AuditLog.action == action)
            count_q = count_q.where(AuditLog.action == action)

        total = (await db.execute(count_q)).scalar()
        result = await db.execute(
            q.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
        )
        rows = result.scalars().all()

        return {
            "logs": [
                {
                    "id": log.id,
                    "user_id": log.user_id,
                    "username": log.username,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "detail": log.detail,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat() if log.created_at else "",
                }
                for log in rows
            ],
            "total": total,
        }


@router.get("/roles")
async def list_roles(_=Depends(require_permission("roles:read"))):
    """获取所有可用角色及权限（需 roles:read 权限）。"""
    return {
        "roles": [
            {
                "key": key,
                "label": label,
                "permissions": get_user_permissions(key),
            }
            for key, label in ROLE_LABELS.items()
        ],
    }
