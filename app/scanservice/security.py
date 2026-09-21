from __future__ import annotations

from hmac import compare_digest

from fastapi import Header, HTTPException

from .config import get_settings


def require_ingest_token(
    authorization: str | None = Header(default=None),
) -> None:
    """Protect Jenkins-to-service callbacks without affecting read-only pages."""
    settings = get_settings()
    if not settings.ingest_token:
        raise HTTPException(
            status_code=503,
            detail="SCAN_SERVICE_INGEST_TOKEN is not configured",
        )
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not compare_digest(token, settings.ingest_token):
        raise HTTPException(status_code=401, detail="invalid ingest token")
