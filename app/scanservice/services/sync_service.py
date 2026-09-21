from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..config import Settings
from ..jenkins import JenkinsClient
from ..sync import _sync_build


def sync_build(
    session: Session,
    client: JenkinsClient,
    settings: Settings,
    build: dict[str, Any],
):
    """Synchronize one Jenkins build while keeping the legacy sync module stable."""
    return _sync_build(session, client, settings, build)
