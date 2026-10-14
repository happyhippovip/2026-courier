"""Read-only Kolibri snapshot.

Three existing sources, and nothing else:

- Muse-Wall slot files on disk
- the Courier ledger journal, through the hub's own projection
- commits already on ``integration/v1`` that record a merged pull request

A source that is missing or unreadable is reported as unavailable. This module
never fills a gap with a stand-in value, and it never writes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

UNAVAILABLE = "UNKNOWN / nicht erreichbar"
MERGED_REF = "integration/v1"
_SLOT_ID = re.compile(r"^MUSE-(\d+)$")
_SQUASH_PR = re.compile(r"\(#(\d+)\)\s*$")
_MERGE_PR = re.compile(r"^Merge pull request #(\d+)\b")
_merge_cache_lock = threading.Lock()
_merge_cache: dict[str, tuple[str, str, list[dict]]] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def station_key(slot_id: str) -> tuple:
    """Slot number, lowest first. Unnumbered names follow, in byte order.

    Directory order is not stable across machines. Number order is: MUSE-2
    stays before MUSE-10, and the same ids always come out in the same order.
    """
    match = _SLOT_ID.fullmatch(slot_id or "")
    if match:
        return (0, int(match.group(1)), slot_id)
    return (1, 10**9, slot_id or "")


def _iso_text(value: str) -> str:
    """Recorded ISO time, written in UTC. Unparseable text is kept as recorded."""
    if not value:
        return UNAVAILABLE
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_unix(value) -> Optional[str]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        return None


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return f"muse-wall/{path.parent.name}/{path.name}"


def _unavailable(source: str, observed_at: str) -> dict:
    return {
        "available": False,
        "source": source,
        "at": UNAVAILABLE,
        "observed_at": observed_at,
        "value": UNAVAILABLE,
    }


def resolve_muse_wall(root: Path) -> tuple[Optional[Path], str]:
    """Use an explicit directory when one is configured.

    When neither ``COURIER_MUSE_WALL_DIR`` nor ``COURIER_WALL_DIR`` is set, the
    slot directory shipped in this repo is the source. A configured directory
    that is not there stays unavailable: another folder is not a substitute.
    """
    configured = os.environ.get("COURIER_MUSE_WALL_DIR") or os.environ.get("COURIER_WALL_DIR")
    if configured:
        path = Path(configured)
        label = "COURIER_MUSE_WALL_DIR" if os.environ.get("COURIER_MUSE_WALL_DIR") else "COURIER_WALL_DIR"
        return (path if path.is_dir() else None), label
    default = root / "scripts" / "windows_muse_wall" / "runtime" / "slots"
    label = "scripts/windows_muse_wall/runtime/slots"
    return (default if default.is_dir() else None), label


def _slot_token(slot_id: str) -> Optional[re.Pattern[str]]:
    if not _SLOT_ID.fullmatch(slot_id or ""):
        return None
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(slot_id)}(?!\d)")


def read_merged_prs(root: Path, observed_at: str) -> dict:
    source = f"git log {MERGED_REF}"
    if not (root / ".git").exists():
        return {**_unavailable(source, observed_at), "rows": []}
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--pretty=format:%H%x1f%cI", MERGED_REF],
            check=True, capture_output=True, text=True, timeout=20,
        )
        head_sha, _, head_at = head.stdout.partition("\x1f")
        head_at = _iso_text(head_at.strip())
        if not head_sha or head_at == UNAVAILABLE:
            return {**_unavailable(source, observed_at), "rows": []}
        cache_key = str(root.resolve())
        with _merge_cache_lock:
            cached = _merge_cache.get(cache_key)
        if cached and cached[0] == head_sha:
            rows = cached[2]
        else:
            log = subprocess.run(
                ["git", "-C", str(root), "log", MERGED_REF, "--pretty=format:%H%x1f%cI%x1f%s"],
                check=True, capture_output=True, text=True, timeout=30,
            )
            rows = _parse_merges(log.stdout, source)
            with _merge_cache_lock:
                _merge_cache[cache_key] = (head_sha, head_at, rows)
    except (OSError, subprocess.SubprocessError):
        return {**_unavailable(source, observed_at), "rows": []}
    listed_at = head_at if head_at else UNAVAILABLE
    return {
        "available": True,
        "source": source,
        "at": listed_at,
        "observed_at": observed_at,
        "value": str(len(rows)),
        "head": head_sha,
        "rows": rows,
    }


def _parse_merges(text: str, source: str) -> list[dict]:
    found: dict[int, dict] = {}
    for line in text.splitlines():
        sha, sep, rest = line.partition("\x1f")
        if not sep:
            continue
        committed_at, sep, subject = rest.partition("\x1f")
        if not sep:
            continue
        match = _SQUASH_PR.search(subject) or _MERGE_PR.search(subject)
        if not match:
            continue
        number = int(match.group(1))
        if number in found:
            continue  # git log is newest first; keep the newest landing
        found[number] = {
            "pr": number,
            "subject": subject,
            "sha": sha,
            "source": source,
            "at": _iso_text(committed_at.strip()),
        }
    return sorted(found.values(), key=lambda row: (row["at"], row["pr"]))


def _done_for(slot_id: str, merged: dict) -> dict:
    source = merged.get("source") or f"git log {MERGED_REF}"
    if not merged.get("available"):
        return {"value": UNAVAILABLE, "source": source, "at": UNAVAILABLE}
    pattern = _slot_token(slot_id)
    hits = []
    if pattern is not None:
        hits = [row for row in merged.get("rows") or [] if pattern.search(row.get("subject") or "")]
    if hits:
        latest = max(hits, key=lambda row: (row.get("at") or "", row.get("pr") or 0))
        return {"value": "DONE", "source": source, "at": latest.get("at") or UNAVAILABLE,
                "pr": latest.get("pr")}
    return {"value": "not done", "source": source, "at": merged.get("at") or UNAVAILABLE}


def read_muse_wall(root: Path, wall: Optional[Path], label: str, observed_at: str, merged: dict) -> dict:
    if wall is None or not wall.is_dir():
        block = _unavailable(label, observed_at)
        block["stations"] = []
        return block
    stations = []
    for path in wall.glob("*/state.json"):
        rel = _display_path(path, root)
        slot_id = path.parent.name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            stations.append({
                "id": slot_id,
                "state": {"value": UNAVAILABLE, "source": rel, "at": UNAVAILABLE},
                "process": {"value": UNAVAILABLE, "source": rel, "at": UNAVAILABLE},
                "done": _done_for(slot_id, merged),
            })
            continue
        if not isinstance(data, dict):
            data = {}
        recorded = data.get("slot_id")
        if isinstance(recorded, str) and recorded.strip():
            slot_id = recorded.strip()
        at = _iso_unix(data.get("updated_at")) or UNAVAILABLE
        state = data.get("state")
        state_value = state.strip()[:80] if isinstance(state, str) and state.strip() else UNAVAILABLE
        process = data.get("process")
        if "process" not in data:
            process_value = UNAVAILABLE
        elif process is None:
            process_value = "none"
        else:
            process_value = "present"
        stations.append({
            "id": slot_id,
            "state": {"value": state_value, "source": rel, "at": at},
            "process": {"value": process_value, "source": rel, "at": at},
            "done": _done_for(slot_id, merged),
        })
    stations.sort(key=lambda station: station_key(station["id"]))
    times = [s["state"]["at"] for s in stations if s["state"]["at"] != UNAVAILABLE]
    return {
        "available": True,
        "source": label,
        "at": max(times) if times else UNAVAILABLE,
        "observed_at": observed_at,
        "value": str(len(stations)),
        "stations": stations,
    }


def read_ledger(view: Optional[dict], observed_at: str) -> dict:
    source = "courier journal (courier.db)"
    if not isinstance(view, dict) or view.get("truth") != "ok":
        block = _unavailable(source, observed_at)
        block["items"] = []
        block["counts"] = {}
        return block
    read_at = view.get("read_at") if isinstance(view.get("read_at"), str) else UNAVAILABLE
    items = []
    for pile in ("needs_you", "working", "done"):
        for card in view.get(pile) or []:
            if not isinstance(card, dict):
                continue
            change = card.get("last_change") if isinstance(card.get("last_change"), dict) else {}
            at = change.get("at") if isinstance(change.get("at"), str) and change.get("at") else UNAVAILABLE
            title = card.get("title") if isinstance(card.get("title"), str) and card.get("title").strip() else UNAVAILABLE
            task_id = card.get("id") if isinstance(card.get("id"), str) and card.get("id") else UNAVAILABLE
            items.append({"id": task_id, "title": title, "pile": pile, "source": source, "at": at})
    counts = view.get("counts") if isinstance(view.get("counts"), dict) else {}
    safe_counts = {}
    for key in ("needs_you", "working", "done"):
        value = counts.get(key)
        safe_counts[key] = value if isinstance(value, int) and not isinstance(value, bool) else UNAVAILABLE
    shown = view.get("done_shown")
    return {
        "available": True,
        "source": source,
        "at": read_at,
        "observed_at": observed_at,
        "value": str(sum(v for v in safe_counts.values() if isinstance(v, int))),
        "counts": safe_counts,
        "done_shown": shown if isinstance(shown, int) and not isinstance(shown, bool) else UNAVAILABLE,
        "items": items,
    }


def build_snapshot(hub, *, root: Optional[Path] = None, wall: Optional[Path] = None,
                   wall_label: Optional[str] = None, observed_at: Optional[str] = None) -> dict:
    """Assemble one snapshot. Each reader fails on its own."""
    root = root or repo_root()
    observed_at = observed_at or utc_now()
    if wall is None and wall_label is None:
        wall, wall_label = resolve_muse_wall(root)
    elif wall_label is None:
        wall_label = _display_path(wall, root) if wall is not None else "muse wall"
    try:
        merged = read_merged_prs(root, observed_at)
    except Exception:  # noqa: BLE001 - one source must not blank the others
        merged = {**_unavailable(f"git log {MERGED_REF}", observed_at), "rows": []}
    try:
        muse = read_muse_wall(root, wall, wall_label or "muse wall", observed_at, merged)
    except Exception:  # noqa: BLE001
        muse = {**_unavailable(wall_label or "muse wall", observed_at), "stations": []}
    try:
        ledger_view = hub.home_view() if hub is not None else None
        ledger = read_ledger(ledger_view, observed_at)
    except Exception:  # noqa: BLE001
        ledger = {**_unavailable("courier journal (courier.db)", observed_at), "items": [], "counts": {}}
    return {"observed_at": observed_at, "muse_wall": muse, "ledger": ledger, "merged_prs": merged}


def snapshot_for_hub(hub) -> dict:
    return build_snapshot(hub)
