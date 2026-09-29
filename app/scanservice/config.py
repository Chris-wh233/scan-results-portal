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


def _string_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _bool_value(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    jenkins_base_url: str
    jenkins_user: str
    jenkins_token: str
    ingest_token: str
    recent_build_limit: int
    request_timeout_seconds: float
    title: str
    page_size: int
    jenkins_jobs: tuple[str, ...] = ()
    discovery_folders: tuple[str, ...] = ()
    discovery_recursive: bool = True

    @property
    def configured_jobs(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(job for job in self.jenkins_jobs if job))

    @classmethod
    def from_environment(cls) -> "Settings":
        config = _read_yaml(os.getenv("SCAN_SERVICE_CONFIG", "/etc/scan-service/config.yaml"))
        jenkins = config.get("jenkins", {})
        discovery = jenkins.get("discovery", {})
        sync = config.get("sync", {})
        ui = config.get("ui", {})

        configured_jobs = _string_list(
            _env_or(jenkins, "jobs", "JENKINS_JOBS", ())
        )
        discovery_jobs = _string_list(discovery.get("extra_jobs"))
        all_jobs = tuple(dict.fromkeys((*configured_jobs, *discovery_jobs)))
        folders = _string_list(
            _env_or(discovery, "folders", "JENKINS_DISCOVERY_FOLDERS", ())
        )

        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite:///./scanservice.db"),
            jenkins_base_url=str(_env_or(jenkins, "base_url", "JENKINS_BASE_URL", "")),
            jenkins_user=os.getenv("JENKINS_USER", ""),
            jenkins_token=os.getenv("JENKINS_TOKEN", ""),
            ingest_token=os.getenv("SCAN_SERVICE_INGEST_TOKEN", ""),
            recent_build_limit=int(
                _env_or(sync, "recent_build_limit", "RECENT_BUILD_LIMIT", 20)
            ),
            request_timeout_seconds=float(
                _env_or(sync, "request_timeout_seconds", "JENKINS_TIMEOUT", 15)
            ),
            title=str(_env_or(ui, "title", "SCAN_SERVICE_TITLE", "Scan Results Portal")),
            page_size=int(ui.get("page_size", 50)),
            jenkins_jobs=all_jobs,
            discovery_folders=folders,
            discovery_recursive=_bool_value(
                _env_or(
                    discovery,
                    "recursive",
                    "JENKINS_DISCOVERY_RECURSIVE",
                    None,
                ),
                True,
            ),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_environment()
