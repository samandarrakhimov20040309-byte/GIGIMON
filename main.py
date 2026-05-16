from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from app.api.router import api_router
from app.core.config import settings
from app.db.engine import create_db_and_tables
from app.jobs.scheduler import start_scheduler

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    scheduler = start_scheduler()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


HTML_PAGES = {".html"}

CSP_HEADER = {
    "Content-Security-Policy": "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://fonts.googleapis.com https://fonts.gstatic.com; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://*.googleapis.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: https:; connect-src 'self' http://127.0.0.1:8000 https://fonts.googleapis.com https://fonts.gstatic.com; worker-src 'self' blob:;"
}


@app.get("/")
def root():
    return Response(
        content=(STATIC_DIR / "index.html").read_text(encoding="utf-8"),
        media_type="text/html",
        headers=CSP_HEADER
    )


@app.get("/{path:path}")
def serve_static(path: str):
    if path in ("login", "api", "ingest", "trades", "auth", "notifications", "reports", "users", "health", "settings", "archive", "analytics", "ai"):
        raise HTTPException(status_code=404, detail="Not found")
    file_path = STATIC_DIR / path
    if file_path.exists():
        if file_path.suffix == ".html":
            return Response(
                content=file_path.read_text(encoding="utf-8"),
                media_type="text/html",
                headers=CSP_HEADER
            )
        mime = {
            ".js": "application/javascript",
            ".css": "text/css",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }.get(file_path.suffix, "application/octet-stream")
        return Response(content=file_path.read_bytes(), media_type=mime)
    return {"detail": "Not found"}, 404

