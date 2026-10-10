from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SrpmEventRequest(BaseModel):
    event: Literal["started", "completed", "failed"]
    jenkins_build_number: int = Field(..., gt=0)
    jenkins_job_full_name: str
    srpm_name: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None
    csmock_exit_code: int | None = None
