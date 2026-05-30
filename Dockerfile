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
# Adds static file serving for Docker deployment
COPY <<'PYEOF' /app/server.py
import sys, os
sys.path.insert(0, "/app")
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.main import app as api_app

# api_app already defines /api/* routes, /assets/* mount (if dist exists),
# and a catch-all / -> index.html. In Docker we serve static from /app/static.
static_dir = "/app/static"
if os.path.isdir(static_dir):
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.isdir(assets_dir):
        api_app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @api_app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(os.path.join(static_dir, "index.html"))

app = api_app
PYEOF

VOLUME ["/app/data"]
EXPOSE 8091
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8091"]
