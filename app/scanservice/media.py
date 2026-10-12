"""Shared helper deciding the HTTP media type for scan artifacts.

The "view" links should render the artifact in the browser; only the
"[download]" links should trigger a download. Browsers download several of
the types these artifacts use (``text/csv``, ``application/json``,
``application/octet-stream`` for ``.log``), so text-like artifacts are served
as ``text/plain`` when viewed.
"""

from __future__ import annotations

import mimetypes


# Artifact types rendered as plain text for the "view" link. ``attachment``
# downloads keep their original media type.
VIEWABLE_TEXT_ARTIFACT_TYPES = frozenset(
    {
        "METADATA",
        "REPORT_JSON",
        "REPORT_CSV",
        "LOG",
        "SUMMARY",
    }
)


def artifact_media_type(*, artifact_type: str, filename: str, download: bool) -> str:
    if not download and artifact_type in VIEWABLE_TEXT_ARTIFACT_TYPES:
        return "text/plain"
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"
