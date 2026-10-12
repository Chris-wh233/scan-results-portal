import pytest

from conftest import FakeJenkinsClient, srpm_archive_bytes

from scanservice.modules.srpm.models import SrpmScanArtifact, SrpmScanTask
from scanservice.modules.srpm.services import artifacts as artifacts_module
from scanservice.modules.srpm.services.artifacts import (
    archive_member_response,
    artifact_response,
)


def _task_with_artifact(session, monkeypatch, name, artifact_type, content):
    task = SrpmScanTask(
        jenkins_job_full_name="csmock-curl-test",
        jenkins_build_number=6,
        srpm_name="curl-8.4.0-9.ocs23.src.rpm",
        scan_result="FINISHED",
        sync_status="SYNCED",
    )
    session.add(task)
    session.flush()
    row = SrpmScanArtifact(
        task=task,
        name=name,
        artifact_type=artifact_type,
        relative_path=name,
    )
    session.add(row)
    session.commit()

    client = FakeJenkinsClient(contents={name: content})
    monkeypatch.setattr(artifacts_module, "JenkinsClient", lambda *args, **kwargs: client)
    return task, row


@pytest.mark.parametrize(
    ("name", "artifact_type"),
    [
        ("scan.ini", "METADATA"),
        ("scan-results-summary.txt", "SUMMARY"),
        ("scan-results.js", "REPORT_JSON"),
        ("scan.log", "LOG"),
    ],
)
def test_view_serves_text_artifacts_inline(session, monkeypatch, name, artifact_type):
    task, row = _task_with_artifact(
        session, monkeypatch, name, artifact_type, b"content\n"
    )

    response = artifact_response(task, row, download=False)

    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["content-disposition"] == f'inline; filename="{name}"'
    assert response.body == b"content\n"


def test_view_of_an_archive_points_to_the_download_link(session, monkeypatch):
    task, row = _task_with_artifact(
        session, monkeypatch, "curl-8.4.0-9.ocs23.tar.xz", "ARCHIVE", b""
    )

    response = artifact_response(task, row, download=False)

    assert b"cannot be viewed online" in response.body


def test_download_of_an_archive_is_an_attachment(session, monkeypatch):
    content = srpm_archive_bytes()
    task, row = _task_with_artifact(
        session, monkeypatch, "curl-8.4.0-9.ocs23.tar.xz", "ARCHIVE", content
    )

    response = artifact_response(task, row, download=True)

    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="curl-8.4.0-9.ocs23.tar.xz"'
    )
    assert response.body == content


def test_archive_member_download_is_an_attachment(session, monkeypatch):
    task, row = _task_with_artifact(
        session, monkeypatch, "curl-8.4.0-9.ocs23.tar.xz", "ARCHIVE", srpm_archive_bytes()
    )

    response = archive_member_response(task, f"{row.relative_path}::scan.log")

    assert response.headers["content-disposition"] == 'attachment; filename="scan.log"'
    assert response.body == b"log\n"
