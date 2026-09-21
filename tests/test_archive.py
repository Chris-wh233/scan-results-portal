import io
import tarfile

import pytest

from scanservice.archive import list_visible_members, read_visible_member


def _archive() -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:xz") as archive:
        for name, content in (
            ("curl-1/scan.ini", b"[scan]\ntool=csmock\n"),
            ("curl-1/scan.log", b"scan complete\n"),
            ("curl-1/debug/details.txt", b"internal\n"),
            ("curl-1/nested/ignored.txt", b"ignored\n"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def test_scan_archive_exposes_only_first_level_non_debug_files():
    content = _archive()

    members = list_visible_members(content)

    assert [(item.name, item.path) for item in members] == [
        ("scan.ini", "curl-1/scan.ini"),
        ("scan.log", "curl-1/scan.log"),
    ]
    assert read_visible_member(content, "curl-1/scan.ini").startswith(b"[scan]")
    with pytest.raises(KeyError):
        read_visible_member(content, "curl-1/debug/details.txt")
