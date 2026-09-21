from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.artifact_service import (
    archive_member_response,
    artifact_response,
    get_artifact_row,
)
from ..services.task_service import get_task


router = APIRouter(prefix="/api/v1/tasks", tags=["artifacts"])


@router.get("/{task_id}/artifacts/{artifact_id}/view")
def view_artifact(task_id: int, artifact_id: int, db: Session = Depends(get_db)) -> Response:
    task = get_task(db, task_id)
    return artifact_response(task, get_artifact_row(task, artifact_id), download=False)


@router.get("/{task_id}/artifacts/{artifact_id}/download")
def download_artifact(task_id: int, artifact_id: int, db: Session = Depends(get_db)) -> Response:
    task = get_task(db, task_id)
    return artifact_response(task, get_artifact_row(task, artifact_id), download=True)


@router.get("/{task_id}/archive/{archive_ref:path}")
def get_archive_member(
    task_id: int, archive_ref: str, db: Session = Depends(get_db)
) -> Response:
    return archive_member_response(get_task(db, task_id), archive_ref)
