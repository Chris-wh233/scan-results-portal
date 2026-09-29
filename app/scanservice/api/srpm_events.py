from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..modules.srpm.services.events import (
    complete_task,
    fail_task,
    find_task,
    register_start,
)
from ..modules.srpm.schemas.events import SrpmEventRequest
from ..security import require_ingest_token
from ..modules.srpm.services.task_service import task_payload


router = APIRouter(prefix="/api/v1/srpm/events", tags=["srpm-events"])


@router.post("")
def receive_srpm_event(
    payload: SrpmEventRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_ingest_token),
) -> dict[str, Any]:
    settings = get_settings()
    values = payload.dict(exclude_unset=True)
    task = find_task(
        db,
        payload.jenkins_job_full_name,
        payload.jenkins_build_number,
    )
    if payload.event == "started":
        task = register_start(db, settings, values)
        db.commit()
    else:
        if task is None:
            task = register_start(db, settings, values)
            db.commit()
        if payload.event == "completed":
            task = complete_task(
                db,
                settings,
                task,
                payload.finished_at,
                payload.csmock_exit_code,
            )
        elif payload.event == "failed":
            task = fail_task(
                db,
                settings,
                task,
                payload.finished_at,
                payload.csmock_exit_code,
            )
            db.commit()
        else:
            raise HTTPException(status_code=422, detail="unsupported SRPM event")
    return task_payload(task)
