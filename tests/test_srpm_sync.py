import json

from sqlalchemy import select

from conftest import FakeJenkinsClient

from scanservice import resync as resync_module
from scanservice.modules.srpm.models import SrpmScanSummary, SrpmScanTask
from scanservice.modules.srpm.services.synchronization import (
    _sync_build,
    sync_registered_tasks,
)


SARIF_DOCUMENT = {
    "version": "2.1.0",
    "runs": [
        {
            "tool": {"driver": {"name": "csdiff", "version": "3.5.4"}},
            "results": [
                {
                    "ruleId": "core.NullDereference",
                    "level": "warning",
                    "message": {"text": "possible null dereference"},
                },
                {
                    "ruleId": "core.NullDereference",
                    "level": "warning",
                    "message": {"text": "possible null dereference"},
                },
            ],
        }
    ],
}


def test_sync_build_uses_sarif_summary_fallback(session, settings):
    archive = "curl-8.4.0-9.ocs23.tar.xz"
    sarif = "csmock-results/curl.sarif"
    artifacts = [
        {"fileName": archive, "relativePath": archive, "size": 1024, "url": None},
        {"fileName": "curl.sarif", "relativePath": sarif, "size": 512, "url": None},
    ]
    client = FakeJenkinsClient(
        artifacts=artifacts,
        contents={
            archive: b"not a tar archive",
            sarif: json.dumps(SARIF_DOCUMENT).encode(),
        },
    )

    task = _sync_build(session, client, settings, 5, job="csmock-curl-test")
    session.commit()

    assert task.srpm_name == "curl-8.4.0-9.ocs23.src.rpm"
    assert task.version == "8.4.0"
    assert task.release == "9.ocs23"
    assert task.nvr == "curl-8.4.0-9.ocs23"
    assert task.scanner == "csdiff"
    assert task.total_findings == 2
    # The archive itself is unusable, so the task is not FINISHED even though
    # the SARIF gave us a summary.
    assert task.scan_result == "NOT_AVAILABLE"
    assert session.scalars(select(SrpmScanSummary)).one().count == 2


def test_sync_build_separates_jobs_with_same_build_number(session, settings):
    client = FakeJenkinsClient()

    _sync_build(session, client, settings, 5, job="packages/curl")
    _sync_build(session, client, settings, 5, job="packages/openssl")
    session.commit()

    tasks = session.scalars(
        select(SrpmScanTask).order_by(SrpmScanTask.jenkins_job_full_name)
    ).all()
    assert [task.jenkins_job_full_name for task in tasks] == [
        "packages/curl",
        "packages/openssl",
    ]


def test_sync_registered_tasks_only_resyncs_unfinished_tasks(
    session, settings, monkeypatch
):
    for build_number, scan_result in (
        (1, "FINISHED"),
        (2, "RUNNING"),
        (3, "NOT_AVAILABLE"),
        (4, "FAILED"),
    ):
        session.add(
            SrpmScanTask(
                jenkins_job_full_name="csmock-curl-test",
                jenkins_build_number=build_number,
                scan_result=scan_result,
                sync_status="PENDING",
            )
        )
    session.commit()

    client = FakeJenkinsClient()
    monkeypatch.setattr(resync_module, "JenkinsClient", lambda *args, **kwargs: client)

    result = sync_registered_tasks(settings, session)

    assert result == {"synced": 2, "failed": 0}
    assert sorted(number for _, number in client.requested_builds) == [2, 3]
    assert client.closed is True
