from __future__ import annotations

from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import ScanFinding, ScanSummary, ScanTask


def set_manifest(task: ScanTask, manifest: dict[str, Any]) -> None:
    for field in (
        "package_name",
        "version",
        "release",
        "nvr",
        "srpm_name",
        "architecture",
        "source_revision",
        "source_url",
        "source_sha256",
        "scanner",
        "scanner_version",
        "mock_config",
        "csmock_exit_code",
        "gate_result",
    ):
        value = manifest.get(field)
        if value is not None:
            setattr(task, field, value)
    plugins = manifest.get("plugins") or manifest.get("enabled_plugins")
    if plugins is not None:
        task.enabled_plugins = plugins
    task.scan_metadata = {**(task.scan_metadata or {}), "manifest": manifest}


def set_ini(task: ScanTask, metadata: dict[str, Any]) -> None:
    for source, target in (
        ("scanner", "scanner"),
        ("scanner_version", "scanner_version"),
        ("mock_config", "mock_config"),
    ):
        if metadata.get(source) and not getattr(task, target):
            setattr(task, target, metadata[source])
    if metadata.get("enabled_plugins") and not task.enabled_plugins:
        task.enabled_plugins = metadata["enabled_plugins"]
    task.scan_metadata = {**(task.scan_metadata or {}), "scan_ini": metadata.get("raw", {})}


def replace_results(
    session: Session,
    task: ScanTask,
    summaries: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
    session.execute(delete(ScanSummary).where(ScanSummary.task_id == task.id))
    session.execute(delete(ScanFinding).where(ScanFinding.task_id == task.id))
    for summary in summaries:
        session.add(
            ScanSummary(
                task_id=task.id,
                checker=str(summary["checker"]),
                issue_type=str(summary["issue_type"]),
                count=int(summary["count"]),
            )
        )
    seen: set[str] = set()
    for finding in findings:
        fingerprint = str(finding["fingerprint"])
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        session.add(ScanFinding(task_id=task.id, **finding))
