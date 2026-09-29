from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..modules.srpm.services.synchronization import sync_once


router = APIRouter(tags=["sync"])


@router.post("/sync")
def sync_tasks(db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return sync_once(get_settings(), db).as_dict()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
