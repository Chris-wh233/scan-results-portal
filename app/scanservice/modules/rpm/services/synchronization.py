from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ....config import Settings
from ....jenkins import JenkinsClient
from ....resync import resync_registered_tasks
from ..domain.state import RPM_FAILED, RPM_FINISHED, RPM_NOT_AVAILABLE, RPM_RUNNING
from ..models import (
    RpmScanArtifact,
    RpmScanComponent,
    RpmScanTask,
    RpmScanVulnerability,
)
from ..parsers.cve_bin_tool import (
    parse_manifest,
    parse_results,
    result_fingerprint,
    summarize,
)


RESULT_FILES = {
    "scan-manifest.json": "METADATA",
    "scan-results.json": "REPORT_JSON",
    "scan-results.csv": "REPORT_CSV",
    "scan-results.html": "REPORT_HTML",
    "scan.log": "LOG",
}
MAX_RESULT_BYTES = 16 * 1024 * 1024


def _cause_user(build: dict[str, Any]) -> str | None:
    for action in build.get("actions") or []:
        for cause in action.get("causes") or []:
            return cause.get("userName") or cause.get("userId") or cause.get(
                "shortDescription"
            )
    return None


def _artifact_name(artifact: dict[str, Any]) -> str:
    return str(artifact.get("relativePath") or artifact.get("fileName") or "")


def _scan_artifacts(task: RpmScanTask, build: dict[str, Any]) -> dict[str, dict[str, Any]]:
    expected_prefix = f"rpm-scan-artifacts/{task.scan_key}/"
    matches = {}
    for artifact in build.get("artifacts") or []:
        path = _artifact_name(artifact)
        basename = path.rsplit("/", 1)[-1]
        if path.startswith(expected_prefix) and basename in RESULT_FILES:
            matches[basename] = artifact
    return matches


def _upsert_artifacts(
    db: Session,
    task: RpmScanTask,
    client: JenkinsClient,
    artifacts: dict[str, dict[str, Any]],
) -> None:
    existing = {row.relative_path: row for row in task.artifacts}
    for basename, artifact in artifacts.items():
        path = _artifact_name(artifact)
        row = existing.get(path)
        if row is None:
            row = RpmScanArtifact(task=task, name=basename, relative_path=path)
            db.add(row)
        row.artifact_type = RESULT_FILES[basename]
        row.size_bytes = artifact.get("size")
        row.jenkins_url = client._url(
            f"{client._job_path(task.jenkins_job_full_name)}/"
            f"{task.jenkins_build_number}/artifact/{path}"
        )


def _read_artifact(
    client: JenkinsClient,
    task: RpmScanTask,
    artifact: dict[str, Any],
) -> bytes:
    size = artifact.get("size")
    if size is not None and int(size) > MAX_RESULT_BYTES:
        raise ValueError(f"artifact is too large to parse: {_artifact_name(artifact)}")
    return client.get_artifact(
        task.jenkins_job_full_name,
        task.jenkins_build_number,
        _artifact_name(artifact),
    )


def _apply_manifest(task: RpmScanTask, manifest: dict[str, Any]) -> None:
    rpm = manifest["rpm"]
    scanner = manifest["scanner"]
    if rpm["sha256"] != task.rpm_sha256:
        raise ValueError("manifest RPM checksum does not match the registered scan")
    task.rpm_name = rpm["filename"]
    task.name = rpm.get("name")
    task.epoch = rpm.get("epoch")
    task.version = rpm.get("version")
    task.release = rpm.get("release")
    task.architecture = rpm.get("architecture")
    task.source_rpm = rpm.get("source_rpm")
    task.rpm_size_bytes = rpm.get("size_bytes")
    task.scanner = scanner.get("name")
    task.scanner_version = scanner.get("version")
    task.scanner_exit_code = scanner.get("exit_code")
    task.scanner_args = scanner.get("args")
    task.scan_metadata = {"manifest": manifest}


def _replace_results(
    db: Session,
    task: RpmScanTask,
    rows: list[dict[str, Any]],
) -> None:
    db.execute(delete(RpmScanComponent).where(RpmScanComponent.task_id == task.id))
    db.execute(
        delete(RpmScanVulnerability).where(RpmScanVulnerability.task_id == task.id)
    )
    summary = summarize(rows)
    for component in summary["components"]:
        db.add(RpmScanComponent(task_id=task.id, **component))
    for row in rows:
        score = row.get("score")
        try:
            parsed_score = float(score) if score not in {None, ""} else None
        except (TypeError, ValueError):
            parsed_score = None
        db.add(
            RpmScanVulnerability(
                task_id=task.id,
                fingerprint=result_fingerprint(row),
                vendor=str(row["vendor"]),
                product=str(row["product"]),
                version=str(row["version"]),
                cve_number=str(row["cve_number"]),
                severity=str(row["severity"]),
                score=parsed_score,
                source=str(row.get("source") or "") or None,
                cvss_version=str(row.get("cvss_version") or "") or None,
                cvss_vector=str(row.get("cvss_vector") or "") or None,
                paths=str(row.get("paths") or "") or None,
                remarks=str(row.get("remarks") or "") or None,
                comments=str(row.get("comments") or "") or None,
                description=str(row.get("description") or "") or None,
                raw=row,
            )
        )
    task.total_vulnerabilities = summary["total"]
    task.component_count = len(summary["components"])
    task.critical_count = summary["critical"]
    task.high_count = summary["high"]
    task.medium_count = summary["medium"]
    task.low_count = summary["low"]
    task.unknown_count = summary["unknown"]


def sync_task(
    db: Session,
    client: JenkinsClient,
    task: RpmScanTask,
) -> RpmScanTask:
    build = client.get_build(task.jenkins_job_full_name, task.jenkins_build_number)
    task.triggered_by = _cause_user(build) or task.triggered_by
    artifacts = _scan_artifacts(task, build)
    _upsert_artifacts(db, task, client, artifacts)
    db.flush()

    required = {"scan-manifest.json", "scan-results.json"}
    if required.issubset(artifacts):
        manifest = parse_manifest(_read_artifact(client, task, artifacts["scan-manifest.json"]))
        results = parse_results(_read_artifact(client, task, artifacts["scan-results.json"]))
        _apply_manifest(task, manifest)
        _replace_results(db, task, results)
        task.state = (
            RPM_FINISHED if task.scanner_exit_code in {0, 1} else RPM_FAILED
        )
        task.sync_status = "SYNCED"
        task.sync_error = None
    elif not build.get("building") and task.state != RPM_FAILED:
        task.state = RPM_NOT_AVAILABLE
        task.sync_status = "ERROR"
        task.sync_error = "Jenkins build has no valid RPM scan manifest and JSON result"
    else:
        task.state = RPM_RUNNING
        task.sync_status = "PENDING"

    task.last_synced_at = datetime.now(timezone.utc)
    return task


def _resync_task(
    db: Session,
    client: JenkinsClient,
    settings: Settings,
    task: RpmScanTask,
) -> RpmScanTask:
    return sync_task(db, client, task)


def sync_registered_tasks(settings: Settings, db: Session) -> dict[str, int]:
    """Re-sync registered RPM tasks that have not reached a terminal state."""
    return resync_registered_tasks(
        settings,
        db,
        model=RpmScanTask,
        state_column=RpmScanTask.state,
        active_states=(RPM_RUNNING, RPM_NOT_AVAILABLE),
        sync_one=_resync_task,
    )
