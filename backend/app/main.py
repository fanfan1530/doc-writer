"""智能文书编写系统 —— FastAPI 入口。"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import generation, models
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        # Mount assets at /assets/
        assets_dir = os.path.join(frontend_dist, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # Serve index.html at root
        @app.get("/")
        async def serve_frontend():
            return FileResponse(os.path.join(frontend_dist, "index.html"))

    return app


app = create_app()
