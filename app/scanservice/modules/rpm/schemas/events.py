from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RpmEventRequest(BaseModel):
    event: Literal["started", "completed", "failed"]
    scan_key: str = Field(..., min_length=1, max_length=128)
    jenkins_build_number: int = Field(..., gt=0)
    jenkins_job_full_name: str = Field(..., min_length=1)
    rpm_name: str = Field(..., min_length=1, max_length=500)
    rpm_sha256: str = Field(..., min_length=64, max_length=64)
    created_at: datetime | None = None
    finished_at: datetime | None = None
    cbt_exit_code: int | None = None
