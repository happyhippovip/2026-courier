"""Known cross-platform test gates already present in this repository.

Each entry cites a test file and a marker string that file must contain.
The checker does not invent failures and does not skip a cited file.
"""

from __future__ import annotations

from pathlib import Path


class CatalogError(ValueError):
    """The catalog does not match the tests it cites."""


ENTRIES: tuple[dict[str, str], ...] = (
    {
        "id": "mac-surface-admission-fcntl",
        "platform": "win32",
        "kind": "skip",
        "test": "tests/test_mac_surface_admission.py",
        "marker": "Mac worker admission tests require Unix (fcntl)",
    },
    {
        "id": "mac-daemon-upload-fcntl",
        "platform": "win32",
        "kind": "skip",
        "test": "tests/test_artifact_upload_flow.py",
        "marker": "Mac daemon requires fcntl",
    },
    {
        "id": "orphan-gate-killpg",
        "platform": "nt",
        "kind": "skip",
        "test": "tests/test_l3_worker_host.py",
        "marker": "POSIX killpg gate; Windows relies on job close semantics",
    },
    {
        "id": "windows-launcher-csc",
        "platform": "windows",
        "kind": "skip",
        "test": "tests/test_windows_launcher_guard.py",
        "marker": "csc.exe not found on this Windows machine",
    },
    {
        "id": "windows-launcher-logs-csc",
        "platform": "windows",
        "kind": "skip",
        "test": "tests/ops/test_windows_launcher_logs.py",
        "marker": "csc.exe not found on this Windows machine",
    },
)

_FIELDS = ("id", "platform", "kind", "test", "marker")


def check_catalog(root: Path, entries: tuple[dict[str, str], ...] | tuple = ENTRIES,
                  *, strict: bool = False) -> dict:
    """Return ok plus one failure per entry that is not backed by its test file.

    strict=True raises CatalogError when the catalog is not ok. A path that
    leaves root, a missing file, a missing marker, a duplicate id, or an empty
    catalog is a failure. The same input yields the same report.
    """
    root = Path(root).resolve()
    failures: list[dict[str, str]] = []
    seen: set[str] = set()
    if not entries:
        failures.append({"id": "", "reason": "catalog is empty"})
    for entry in entries:
        reason = _entry_failure(root, entry, seen)
        if reason is not None:
            failures.append({"id": str(entry.get("id", "")), "reason": reason})
    report = {"ok": not failures, "failures": failures, "entries": [dict(item) for item in entries]}
    if strict and failures:
        raise CatalogError("; ".join(f"{item['id'] or '-'}: {item['reason']}" for item in failures))
    return report


def _entry_failure(root: Path, entry: dict, seen: set[str]) -> str | None:
    if not isinstance(entry, dict):
        return "entry is not an object"
    for field in _FIELDS:
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"missing {field}"
    entry_id = entry["id"]
    if entry_id in seen:
        return "duplicate id"
    seen.add(entry_id)
    relative = Path(entry["test"])
    if relative.is_absolute() or ".." in relative.parts:
        return "test path escapes the catalog root"
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return "test path escapes the catalog root"
    if not path.is_file():
        return "cited test is missing"
    text = path.read_text(encoding="utf-8")
    if entry["marker"] not in text:
        return "marker is not in the cited test"
    return None
