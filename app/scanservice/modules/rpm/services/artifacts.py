from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse

from ....config import get_settings
from ....jenkins import JenkinsClient
from ....media import artifact_media_type
from ..models import RpmScanArtifact, RpmScanTask


def get_artifact(task: RpmScanTask, artifact_id: int) -> RpmScanArtifact:
    artifact = next((row for row in task.artifacts if row.id == artifact_id), None)
    if artifact is None:
        raise HTTPException(status_code=404, detail="RPM scan artifact not found")
    return artifact


def artifact_response(
    task: RpmScanTask,
    artifact: RpmScanArtifact,
    *,
    download: bool,
) -> Response:
    settings = get_settings()
    max_bytes = settings.artifact_limits.max_download_bytes
    if artifact.size_bytes is not None and artifact.size_bytes > max_bytes:
        raise HTTPException(status_code=413, detail="artifact is too large to serve")
    client = JenkinsClient(
        settings.jenkins_base_url,
        settings.jenkins_user,
        settings.jenkins_token,
        settings.request_timeout_seconds,
    )
    job_name = task.jenkins_job_full_name
    build_number = task.jenkins_build_number
    relative_path = artifact.relative_path

    def body():
        try:
            yield from client.iter_artifact(
                job_name,
                build_number,
                relative_path,
                max_bytes=max_bytes,
            )
        finally:
            client.close()

    media_type = artifact_media_type(
        artifact_type=artifact.artifact_type,
        filename=artifact.name,
        download=download,
    )
    disposition = "attachment" if download else "inline"
    headers = {
        "Content-Disposition": f'{disposition}; filename="{artifact.name.replace(chr(34), chr(39))}"'
    }
    if not download and artifact.artifact_type == "REPORT_HTML":
        headers["Content-Security-Policy"] = (
            "sandbox allow-scripts; "
            "default-src 'none'; "
            "script-src 'unsafe-inline'; "
            "style-src 'unsafe-inline'; "
            "img-src data: blob:; "
            "connect-src 'none'"
        )
    return StreamingResponse(content=body(), media_type=media_type, headers=headers)
