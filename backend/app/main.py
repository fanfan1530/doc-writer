"""智能文书编写系统 —— FastAPI 入口。"""

import logging
import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import auth, copilot, generation, models
from app.config import get_settings
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.error_handler import (
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)

# 结构化日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
    )

    # 请求 ID 中间件（最外层，最先执行）
    app.add_middleware(RequestIDMiddleware)

    # JWT 认证中间件
    from app.middleware.auth import AuthMiddleware
    app.add_middleware(AuthMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局异常处理
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # 启动时初始化数据库 + 默认用户
    @app.on_event("startup")
    async def on_startup():
        from app.infrastructure.database import init_db
        await init_db()
        from app.infrastructure.data_migration import migrate_json_to_db
        await migrate_json_to_db()
        await _seed_default_admin()

    # 监控（必须在 app 启动前注册 middleware）
    from app.core.monitoring import setup_monitoring
    setup_monitoring(app)

    # 路由
    app.include_router(auth.router)
    app.include_router(copilot.router)
    app.include_router(generation.router)
    app.include_router(models.router)

    @app.get("/api/health")
    async def health_check():
        return {"status": "ok", "app": settings.app_name, "version": settings.app_version}

    # ---- 托管前端静态文件（无需 Node.js）----
    frontend_dist = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    )
    if os.path.isdir(frontend_dist):
        assets_dir = os.path.join(frontend_dist, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/")
        async def serve_frontend():
            return FileResponse(os.path.join(frontend_dist, "index.html"))

    return app


async def _seed_default_admin():
    """首次启动时创建默认管理员账户（admin/admin123）。"""
    try:
        from app.infrastructure.database import AsyncSessionLocal
        from app.infrastructure.models import User
        from app.core.auth import hash_password
        from sqlalchemy import select, func

        async with AsyncSessionLocal() as db:
            count = (await db.execute(select(func.count()).select_from(User))).scalar()
            if count == 0:
                db.add(User(
                    username="admin",
                    hashed_password=hash_password("admin123"),
                    role="admin",
                ))
                await db.commit()
    except Exception:
        pass  # 用户表可能尚未创建


app = create_app()
