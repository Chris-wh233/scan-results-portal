from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def _read_yaml(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_file():
        return {}
    with config_path.open("r", encoding="utf-8") as stream:
        loaded = yaml.safe_load(stream)
    return loaded if isinstance(loaded, dict) else {}


def _env_or(mapping: dict[str, Any], key: str, env_name: str, default: Any) -> Any:
    value = os.getenv(env_name)
    if value not in {None, ""}:
        return value
    return mapping.get(key, default)


@dataclass(frozen=True)
class Settings:
    database_url: str
    jenkins_base_url: str
    jenkins_user: str
    jenkins_token: str
    ingest_token: str
    operator_token: str
    operator_sync_rate_limit: int
    recent_build_limit: int
    request_timeout_seconds: float
    title: str
    page_size: int

    @classmethod
    def from_environment(cls) -> "Settings":
        config = _read_yaml(os.getenv("SCAN_SERVICE_CONFIG", "/etc/scan-service/config.yaml"))
        jenkins = config.get("jenkins", {})
        sync = config.get("sync", {})
        ui = config.get("ui", {})

        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite:///./scanservice.db"),
            jenkins_base_url=str(_env_or(jenkins, "base_url", "JENKINS_BASE_URL", "")),
            jenkins_user=os.getenv("JENKINS_USER", ""),
            jenkins_token=os.getenv("JENKINS_TOKEN", ""),
            ingest_token=os.getenv("SCAN_SERVICE_INGEST_TOKEN", ""),
            operator_token=os.getenv("SCAN_SERVICE_OPERATOR_TOKEN", ""),
            operator_sync_rate_limit=int(
                os.getenv("OPERATOR_SYNC_RATE_LIMIT_PER_MINUTE", "6")
            ),
            recent_build_limit=int(
                _env_or(sync, "recent_build_limit", "RECENT_BUILD_LIMIT", 20)
            ),
            request_timeout_seconds=float(
                _env_or(sync, "request_timeout_seconds", "JENKINS_TIMEOUT", 15)
            ),
            title=str(_env_or(ui, "title", "SCAN_SERVICE_TITLE", "Scan Results Portal")),
            page_size=int(ui.get("page_size", 50)),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_environment()
