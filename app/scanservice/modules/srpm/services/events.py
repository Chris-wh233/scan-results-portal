from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ....config import Settings
from ....jenkins import JenkinsClient
from ..models import SrpmScanTask
from .synchronization import sync_build
from .task_service import apply_task_fields
from ..domain.state import (
    SRPM_FAILED,
    SRPM_FINISHED,
    SRPM_NOT_AVAILABLE,
    SRPM_RUNNING,
    result_after_failure,
)


def _job_name(settings: Settings, values: dict[str, Any]) -> str:
    job = str(values.get("jenkins_job_full_name") or "")
    if not job:
        raise ValueError("Jenkins job is required")
    return job


def find_task(db: Session, job: str, build_number: int) -> SrpmScanTask | None:
    return db.scalar(
        select(SrpmScanTask).where(
            SrpmScanTask.jenkins_job_full_name == job,
            SrpmScanTask.jenkins_build_number == build_number,
        )
    )


def _ensure_task(
    db: Session, settings: Settings, values: dict[str, Any]
) -> SrpmScanTask:
    job = _job_name(settings, values)
    build_number = int(values["jenkins_build_number"])
    task = find_task(db, job, build_number)
    if task is None:
        task = SrpmScanTask(
            jenkins_job_full_name=job,
            jenkins_build_number=build_number,
            lifecycle_state="DISCOVERED",
            scan_result=SRPM_NOT_AVAILABLE,
            gate_result="NOT_EVALUATED",
            sync_status="PENDING",
        )
        db.add(task)
        db.flush()
    return task


def register_start(
    db: Session, settings: Settings, values: dict[str, Any]
) -> SrpmScanTask:
    task = _ensure_task(db, settings, values)
    apply_task_fields(task, values)
    occurred_at = values.get("created_at") or datetime.now(timezone.utc)

    # A retried start callback may arrive after a terminal event. Preserve the
    # terminal result while still accepting metadata from the retry.
    if task.scan_result not in {SRPM_FINISHED, SRPM_FAILED}:
        task.lifecycle_state = "RUNNING"
        task.scan_result = SRPM_RUNNING
        task.created_at = task.created_at or occurred_at
        task.started_at = task.started_at or occurred_at
        task.scan_started_at = task.scan_started_at or occurred_at
        task.scan_finished_at = None
        task.finished_at = None
    task.sync_error = None
    return task


def complete_task(
    db: Session,
    settings: Settings,
    task: SrpmScanTask,
    finished_at: datetime | None = None,
    exit_code: int | None = None,
) -> SrpmScanTask:
    ended_at = finished_at or datetime.now(timezone.utc)
    task.scan_finished_at = ended_at
    task.finished_at = ended_at
    task.sync_status = "PENDING"
    if exit_code is not None:
        task.csmock_exit_code = exit_code
    db.commit()

    client = JenkinsClient(
        settings.jenkins_base_url,
        settings.jenkins_user,
        settings.jenkins_token,
        settings.request_timeout_seconds,
    )
    try:
        build = client.get_build(task.jenkins_job_full_name, task.jenkins_build_number)
        sync_build(
            db,
            client,
            settings,
            build,
            job_full_name=task.jenkins_job_full_name,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        task = find_task(db, task.jenkins_job_full_name, task.jenkins_build_number)
        if task is None:
            raise
        if task.scan_result != SRPM_FAILED:
            task.scan_result = SRPM_NOT_AVAILABLE
        task.sync_status = "ERROR"
        task.sync_error = str(exc)[:4000]
        task.last_synced_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        client.close()
    return task


def fail_task(
    db: Session,
    settings: Settings,
    task: SrpmScanTask,
    finished_at: datetime | None = None,
    exit_code: int | None = None,
) -> SrpmScanTask:
    ended_at = finished_at or datetime.now(timezone.utc)
    task.scan_result = result_after_failure()
    task.scan_finished_at = ended_at
    task.finished_at = ended_at
    task.sync_status = "SYNCED"
    task.sync_error = None
    if exit_code is not None:
        task.csmock_exit_code = exit_code
    return task
