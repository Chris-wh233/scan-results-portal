from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ScanState = Literal["RUNNING", "FINISHED", "FAILED", "NOT_AVAILABLE"]


class TaskCreateRequest(BaseModel):
    jenkins_build_number: int = Field(..., gt=0)
    jenkins_job_full_name: str | None = None
    jenkins_build_url: str | None = None
    created_at: datetime | None = None
    package_name: str | None = None
    version: str | None = None
    release: str | None = None
    nvr: str | None = None
    srpm_name: str | None = None
    architecture: str | None = None
    source_revision: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    jenkins_node: str | None = None
    triggered_by: str | None = None
    scanner: str | None = None
    scanner_version: str | None = None
    mock_config: str | None = None
    enabled_plugins: list[str] | None = None


class TaskUpdateRequest(BaseModel):
    jenkins_build_url: str | None = None
    package_name: str | None = None
    version: str | None = None
    release: str | None = None
    nvr: str | None = None
    srpm_name: str | None = None
    architecture: str | None = None
    source_revision: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    lifecycle_state: str | None = None
    execution_result: str | None = None
    scan_result: ScanState | None = None
    gate_result: str | None = None
    jenkins_node: str | None = None
    triggered_by: str | None = None
    scanner: str | None = None
    scanner_version: str | None = None
    mock_config: str | None = None
    enabled_plugins: list[str] | None = None
    csmock_exit_code: int | None = None
    total_findings: int | None = Field(default=None, ge=0)


class ScanEventRequest(BaseModel):
    finished_at: datetime | None = None
