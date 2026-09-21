import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from scanservice.config import Settings
from scanservice.db import Base
from scanservice.models import ScanSummary, ScanTask
from scanservice.sync import _sync_build


class FakeJenkinsClient:
    def __init__(self, detail, artifacts):
        self.detail = detail
        self.artifacts = artifacts

    def get_build(self, job, number):
        return self.detail

    def get_artifact(self, job, number, path):
        return json.dumps(
            {
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
        ).encode()

    def _url(self, value):
        return value

    def close(self):
        pass


def test_sync_build_uses_sarif_summary_fallback():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    artifacts = [
        {
            "fileName": "curl-8.4.0-9.ocs23.tar.xz",
            "relativePath": "curl-8.4.0-9.ocs23.tar.xz",
            "size": 1024,
            "url": "http://jenkins/job/csmock-curl-test/5/artifact/curl-8.4.0-9.ocs23.tar.xz",
        },
        {
            "fileName": "curl.sarif",
            "relativePath": "csmock-results/curl.sarif",
            "size": 512,
            "url": "http://jenkins/job/csmock-curl-test/5/artifact/csmock-results/curl.sarif",
        }
    ]
    client = FakeJenkinsClient(
        {
            "number": 5,
            "url": "http://jenkins/job/csmock-curl-test/5/",
            "timestamp": 1_700_000_000_000,
            "duration": 2_000,
            "building": False,
            "result": "SUCCESS",
            "artifacts": artifacts,
            "actions": [],
        },
        artifacts,
    )
    settings = Settings(
        database_url="sqlite://",
        jenkins_base_url="http://jenkins",
        jenkins_user="",
        jenkins_token="",
        ingest_token="",
        jenkins_job="csmock-curl-test",
        scan_stage="",
        recent_build_limit=5,
        request_timeout_seconds=5,
        title="Test",
        page_size=50,
    )

    task = _sync_build(session, client, settings, {"number": 5})
    session.commit()

    assert task.srpm_name == "curl-8.4.0-9.ocs23.src.rpm"
    assert task.version == "8.4.0"
    assert task.release == "9.ocs23"
    assert task.nvr == "curl-8.4.0-9.ocs23"
    assert task.scanner == "csdiff"
    assert task.total_findings == 2
    assert task.scan_result == "NOT_AVAILABLE"
    assert session.scalars(select(ScanSummary)).one().count == 2
