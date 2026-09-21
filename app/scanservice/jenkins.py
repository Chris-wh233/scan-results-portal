from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx


class JenkinsError(RuntimeError):
    pass


class JenkinsClient:
    def __init__(
        self,
        base_url: str,
        user: str = "",
        token: str = "",
        timeout: float = 15,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            auth=(user, token) if user or token else None,
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _job_path(job_name: str) -> str:
        parts = [part for part in job_name.strip("/").split("/") if part]
        return "/".join(f"job/{quote(part, safe='')}" for part in parts)

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.client.get(self._url(path), params=params)
        if response.status_code >= 400:
            raise JenkinsError(
                f"Jenkins returned HTTP {response.status_code} for {path}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise JenkinsError(f"Jenkins returned non-JSON data for {path}") from exc

    def list_builds(self, job_name: str, limit: int) -> list[dict[str, Any]]:
        data = self._get_json(
            f"{self._job_path(job_name)}/api/json",
            {
                "tree": "builds[number,url,result,building,timestamp,duration]",
            },
        )
        builds = data.get("builds") or []
        return builds[:limit]

    def get_build(self, job_name: str, number: int) -> dict[str, Any]:
        return self._get_json(
            f"{self._job_path(job_name)}/{number}/api/json",
            {
                "tree": (
                    "number,url,result,building,timestamp,duration,"
                    "displayName,artifacts[fileName,relativePath,size,url],"
                    "actions[causes[userId,userName,shortDescription]]"
                ),
            },
        )

    def get_artifact(self, job_name: str, number: int, relative_path: str) -> bytes:
        path = "/".join(
            quote(part, safe="") for part in relative_path.strip("/").split("/")
        )
        response = self.client.get(
            self._url(f"{self._job_path(job_name)}/{number}/artifact/{path}")
        )
        if response.status_code >= 400:
            raise JenkinsError(
                f"Jenkins returned HTTP {response.status_code} for artifact {relative_path}"
            )
        return response.content
