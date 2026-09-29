from __future__ import annotations

from typing import Final, Literal


SrpmScanState = Literal["RUNNING", "FINISHED", "FAILED", "NOT_AVAILABLE"]

SRPM_RUNNING: Final = "RUNNING"
SRPM_FINISHED: Final = "FINISHED"
SRPM_FAILED: Final = "FAILED"
SRPM_NOT_AVAILABLE: Final = "NOT_AVAILABLE"


def result_after_failure() -> str:
    return SRPM_FAILED


def result_after_valid_archive() -> str:
    return SRPM_FINISHED


def result_after_unavailable_archive(*, building: bool, ended: bool) -> str:
    if building and not ended:
        return SRPM_RUNNING
    return SRPM_NOT_AVAILABLE
