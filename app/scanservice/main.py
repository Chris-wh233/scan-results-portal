from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.artifacts import router as artifacts_router
from .api.health import router as health_router
from .api.ingest import router as ingest_router
from .api.sync import router as sync_router
from .api.tasks import router as tasks_router
from .config import get_settings
from .db import SessionLocal
from .sync import sync_once
from .web.routes import router as web_router


settings = get_settings()
app = FastAPI(title=settings.title)
app.mount("/static", StaticFiles(directory="/app/scanservice/static"), name="static")

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(tasks_router)
app.include_router(artifacts_router)
app.include_router(sync_router)
app.include_router(web_router)


def sync_from_cli() -> dict[str, int]:
    """Compatibility helper for callers that used the old main module."""
    with SessionLocal() as db:
        return sync_once(settings, db).as_dict()
