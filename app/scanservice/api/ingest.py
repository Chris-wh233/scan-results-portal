from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..jenkins import JenkinsClient
from ..models import ScanTask
from ..schemas.tasks import ScanEventRequest, TaskCreateRequest, TaskUpdateRequest
from ..security import require_ingest_token
from ..services.sync_service import sync_build
from ..services.task_service import apply_task_fields, get_task, task_payload


router = APIRouter(prefix="/api/v1/tasks", tags=["ingest"])


@router.post("", status_code=201)
def register_task(
    payload: TaskCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_ingest_token),
) -> dict[str, int]:
    settings = get_settings()
    job = payload.jenkins_job_full_name or settings.jenkins_job
    if not job:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Jenkins job is required")

    task = db.scalar(
        select(ScanTask).where(
            ScanTask.jenkins_job_full_name == job,
            ScanTask.jenkins_build_number == payload.jenkins_build_number,
        )
    )
    if task is None:
        task = ScanTask(
            jenkins_job_full_name=job,
            jenkins_build_number=payload.jenkins_build_number,
            lifecycle_state="RUNNING",
            scan_result="RUNNING",
            gate_result="NOT_EVALUATED",
            sync_status="PENDING",
        )
        db.add(task)
    apply_task_fields(task, payload.dict(exclude_unset=True))
    started_at = payload.created_at or datetime.now(timezone.utc)
    task.lifecycle_state = "RUNNING"
    task.scan_result = "RUNNING"
    task.created_at = started_at
    task.started_at = started_at
    task.scan_started_at = started_at
    task.scan_finished_at = None
    task.finished_at = None
    task.sync_error = None
    db.commit()
    db.refresh(task)
    return {"id": task.id}


@router.patch("/{task_id}")
def update_task(
    task_id: int,
    payload: TaskUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_ingest_token),
) -> dict[str, Any]:
    task = get_task(db, task_id)
    apply_task_fields(task, payload.dict(exclude_unset=True))
    db.commit()
    return task_payload(task)


@router.post("/{task_id}/scan-complete")
def mark_scan_complete(
    task_id: int,
    payload: ScanEventRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_ingest_token),
) -> dict[str, Any]:
    settings = get_settings()
    task = get_task(db, task_id)
    finished_at = payload.finished_at or datetime.now(timezone.utc)
    task.scan_finished_at = finished_at
    task.finished_at = finished_at
    task.sync_status = "PENDING"
    db.commit()

    client = JenkinsClient(
        settings.jenkins_base_url,
        settings.jenkins_user,
        settings.jenkins_token,
        settings.request_timeout_seconds,
    )
    try:
        build = client.get_build(task.jenkins_job_full_name, task.jenkins_build_number)
        sync_build(db, client, settings, build)
        db.commit()
    except Exception as exc:
        db.rollback()
        task = get_task(db, task_id)
        if task.scan_result != "FAILED":
            task.scan_result = "NOT_AVAILABLE"
        task.sync_status = "ERROR"
        task.sync_error = str(exc)[:4000]
        task.last_synced_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        client.close()
    return task_payload(get_task(db, task_id))


@router.post("/{task_id}/scan-failed")
def mark_scan_failed(
    task_id: int,
    payload: ScanEventRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_ingest_token),
) -> dict[str, Any]:
    task = get_task(db, task_id)
    finished_at = payload.finished_at or datetime.now(timezone.utc)
    task.scan_result = "FAILED"
    task.scan_finished_at = finished_at
    task.finished_at = finished_at
    task.sync_status = "SYNCED"
    task.sync_error = None
    db.commit()
    return task_payload(task)
