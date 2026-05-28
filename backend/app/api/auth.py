"""认证 API —— 登录、注册、Token 刷新。"""

from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.security import get_user_permissions, ROLE_LABELS
from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.models import User
from sqlalchemy import select

router = APIRouter(prefix="/api/auth", tags=["认证"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(...)


def _login_response(user: User) -> dict:
    access_token = create_access_token(user.username, user.id, user.role)
    refresh_token = create_refresh_token(user.username)
    permissions = get_user_permissions(user.role)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, "未知"),
        "permissions": permissions,
        "display_name": user.display_name or user.username,
        "unit": user.unit or "",
    }


@router.post("/login")
async def login(body: LoginRequest):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == body.username)
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(body.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账户已被禁用",
            )

        return _login_response(user)


@router.post("/register")
async def register(body: RegisterRequest):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == body.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名已存在",
            )

        user = User(
            username=body.username,
            hashed_password=hash_password(body.password),
            role="user",
        )
        db.add(user)
        await db.commit()

        return _login_response(user)


@router.post("/refresh")
async def refresh_token(body: RefreshRequest):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )

    username = payload.get("sub", "")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已被禁用",
            )

        access_token = create_access_token(user.username, user.id, user.role)
        refresh_token = create_refresh_token(user.username)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }


@router.get("/me")
async def get_current_user(request: Request):
    """获取当前登录用户信息。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "role_label": ROLE_LABELS.get(user.role, "未知"),
            "permissions": get_user_permissions(user.role),
            "display_name": user.display_name or user.username,
            "unit": user.unit or "",
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else "",
        }
