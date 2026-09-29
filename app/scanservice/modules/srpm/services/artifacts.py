from __future__ import annotations

import mimetypes
import tarfile

from fastapi import HTTPException
from fastapi.responses import HTMLResponse, Response

from ..csmock.archive import list_visible_members, read_visible_member
from ....config import get_settings
from ....jenkins import JenkinsClient
from ..models import SrpmScanArtifact, SrpmScanTask


def get_artifact_row(task: SrpmScanTask, artifact_id: int) -> SrpmScanArtifact:
    row = next((item for item in task.artifacts if item.id == artifact_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return row


def read_artifact_content(task: SrpmScanTask, row: SrpmScanArtifact) -> bytes:
    source_path = row.relative_path
    member_path = None
    if "::" in source_path:
        source_path, _, member_path = source_path.partition("::")
        archive_row = next(
            (
                item
                for item in task.artifacts
                if item.relative_path == source_path and "::" not in item.relative_path
            ),
            None,
        )
        if archive_row is None:
            raise HTTPException(status_code=404, detail="source archive not found")

    if not task.jenkins_job_full_name or task.jenkins_build_number is None:
        raise HTTPException(status_code=404, detail="artifact source not found")

    settings = get_settings()
    client = JenkinsClient(
        settings.jenkins_base_url,
        settings.jenkins_user,
        settings.jenkins_token,
        settings.request_timeout_seconds,
    )
    try:
        content = client.get_artifact(
            task.jenkins_job_full_name, task.jenkins_build_number, source_path
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"unable to read artifact: {exc}") from exc
    finally:
        client.close()

    if member_path is None:
        return content
    try:
        visible = {item.path for item in list_visible_members(content)}
        if member_path not in visible:
            raise KeyError(member_path)
        return read_visible_member(content, member_path)
    except (KeyError, OSError, ValueError, tarfile.TarError) as exc:
        raise HTTPException(status_code=404, detail="archive member not found") from exc


def artifact_response(task: SrpmScanTask, row: SrpmScanArtifact, *, download: bool) -> Response:
    filename = (row.name or "artifact").replace('"', "'")
    if not download and row.artifact_type == "ARCHIVE":
        return HTMLResponse(
            "<p>This artifact cannot be viewed online. "
            "Use the <b>[download]</b> link to download it.</p>"
        )
    content = read_artifact_content(task, row)
    if row.artifact_type in {"LOG", "METADATA", "SUMMARY", "REPORT_JSON"}:
        media_type = "text/plain"
    else:
        media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    disposition = "attachment" if download else "inline"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


def archive_member_response(task: SrpmScanTask, archive_ref: str) -> Response:
    archive_path, separator, member_path = archive_ref.partition("::")
    if not separator or not archive_path or not member_path:
        raise HTTPException(status_code=404, detail="invalid archive member")

    archive_row = next(
        (
            row
            for row in task.artifacts
            if row.relative_path == archive_path and "::" not in row.relative_path
        ),
        None,
    )
    if archive_row is None or not task.jenkins_job_full_name or task.jenkins_build_number is None:
        raise HTTPException(status_code=404, detail="archive not found")

    settings = get_settings()
    client = JenkinsClient(
        settings.jenkins_base_url,
        settings.jenkins_user,
        settings.jenkins_token,
        settings.request_timeout_seconds,
    )
    try:
        content = client.get_artifact(
            task.jenkins_job_full_name, task.jenkins_build_number, archive_path
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"unable to read archive: {exc}") from exc
    finally:
        client.close()

    try:
        visible = {item.path for item in list_visible_members(content)}
        if member_path not in visible:
            raise KeyError(member_path)
        member_content = read_visible_member(content, member_path)
    except (KeyError, OSError, ValueError, tarfile.TarError) as exc:
        raise HTTPException(status_code=404, detail="archive member not found") from exc

    filename = member_path.rsplit("/", 1)[-1]
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=member_content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
