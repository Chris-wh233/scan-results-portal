from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ScanTask
from ..services.task_service import get_task, list_task_page, task_payload


router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("")
def list_tasks(
    search: str | None = None,
    scan_result: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    total, rows = list_task_page(db, search, scan_result, page, page_size)
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": [task_payload(row) for row in rows],
    }


@router.get("/{task_id}")
def get_task_api(task_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return task_payload(get_task(db, task_id))


@router.get("/{task_id}/summary")
def get_summary(task_id: int, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    task = get_task(db, task_id)
    return [
        {"checker": row.checker, "issue_type": row.issue_type, "count": row.count}
        for row in task.summaries
    ]


@router.get("/{task_id}/findings")
def get_findings(task_id: int, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    task = get_task(db, task_id)
    return [
        {
            "id": row.id,
            "fingerprint": row.fingerprint,
            "checker": row.checker,
            "rule_id": row.rule_id,
            "severity": row.severity,
            "message": row.message,
            "file_path": row.file_path,
            "line": row.line,
            "column": row.column,
            "code_context": row.code_context,
            "raw": row.raw,
        }
        for row in task.findings
    ]


@router.get("/{task_id}/artifacts")
def get_artifacts(task_id: int, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    task = get_task(db, task_id)
    return [
        {
            "id": row.id,
            "name": row.name,
            "artifact_type": row.artifact_type,
            "relative_path": row.relative_path,
            "url": row.jenkins_url,
            "size_bytes": row.size_bytes,
        }
        for row in task.artifacts
    ]
