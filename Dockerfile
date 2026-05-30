FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt aiofiles

COPY backend/app ./app
COPY backend/.env .
COPY frontend/dist ./static

# Database (also mountable as volume at runtime)
RUN mkdir -p /app/data
COPY backend/app/knowledge/data.db /app/data/data.db

# Entry point: uses api_app directly (routes already have /api prefix)
# Adds static file serving + SPA fallback for Docker deployment
COPY <<'PYEOF' /app/server.py
import sys, os
sys.path.insert(0, "/app")
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.main import app as api_app

# In Docker we serve static from /app/static, with SPA fallback.
static_dir = "/app/static"
if os.path.isdir(static_dir):
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.isdir(assets_dir):
        api_app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @api_app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(os.path.join(static_dir, "index.html"))

    # SPA fallback: serve index.html for any non-API, non-asset path
    @api_app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(request: Request, full_path: str):
        # Don't catch API or asset paths (these are handled by earlier routes)
        if full_path.startswith("api/") or full_path.startswith("assets/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return FileResponse(os.path.join(static_dir, "index.html"))

app = api_app
PYEOF

VOLUME ["/app/data"]
EXPOSE 8091
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8091"]
