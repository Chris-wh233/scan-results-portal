from .config import get_settings
from .db import SessionLocal
from .sync import sync_once


if __name__ == "__main__":
    settings = get_settings()
    with SessionLocal() as session:
        print(sync_once(settings, session).as_dict())
