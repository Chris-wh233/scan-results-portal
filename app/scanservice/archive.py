from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import PurePosixPath
import tarfile


@dataclass(frozen=True)
class ArchiveMember:
    """A visible file from the scan result archive."""

    path: str
    name: str
    size: int


def _parts(path: str) -> tuple[str, ...] | None:
    path = path.replace("\\", "/")
    if path.startswith("/"):
        return None
    parts = tuple(part for part in PurePosixPath(path).parts if part not in {".", ""})
    if not parts or ".." in parts:
        return None
    return parts


def _visible_member(member: tarfile.TarInfo) -> ArchiveMember | None:
    if not member.isfile():
        return None
    parts = _parts(member.name)
    if parts is None:
        return None

    # csmock archives normally contain NVR/<file>.  Only expose files directly
    # below that directory and deliberately omit NVR/debug/....  Supporting a
    # flat archive as well keeps the reader tolerant of custom Jenkins steps.
    if len(parts) == 1:
        display_name = parts[0]
    else:
        if len(parts) != 2 or parts[1] == "debug":
            return None
        display_name = parts[1]
    return ArchiveMember(path="/".join(parts), name=display_name, size=member.size)


def list_visible_members(content: bytes) -> list[ArchiveMember]:
    visible: list[ArchiveMember] = []
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
        for member in archive.getmembers():
            item = _visible_member(member)
            if item is not None:
                visible.append(item)
    return sorted(visible, key=lambda item: (item.name, item.path))


def read_visible_member(content: bytes, member_path: str) -> bytes:
    """Read one member after applying the same visibility/path checks."""
    requested = _parts(member_path)
    if requested is None:
        raise KeyError(member_path)
    normalized = "/".join(requested)
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
        for member in archive.getmembers():
            item = _visible_member(member)
            if item is None or item.path != normalized:
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                break
            return extracted.read()
    raise KeyError(member_path)
