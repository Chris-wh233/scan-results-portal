from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api.artifacts import router as artifacts_router
from .api.health import router as health_router
from .api.srpm_events import router as srpm_events_router
from .api.sync import router as sync_router
from .api.tasks import router as tasks_router
from .config import get_settings
from .web.routes import router as web_router


settings = get_settings()
app = FastAPI(title=settings.title)
app.mount("/static", StaticFiles(directory="/app/scanservice/static"), name="static")

app.include_router(health_router)
app.include_router(srpm_events_router)
app.include_router(tasks_router, prefix="/api/v1/srpm/tasks")
app.include_router(artifacts_router, prefix="/api/v1/srpm/tasks")
app.include_router(sync_router, prefix="/api/v1/srpm")
app.include_router(web_router)
