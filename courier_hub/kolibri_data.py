"""Read-only Kolibri snapshot.

One flower per source. The bird is allowed to fly only when that source shows
evidenced activity. A missing source stays UNKNOWN. This module never writes
and never substitutes a value the source did not record.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

UNAVAILABLE = "UNKNOWN / nicht erreichbar"
REST_TEXT = "Keine Aktivität"
PAUSE = "Pause"
MERGED_REF = "integration/v1"
HEARTBEAT_S = 60
_SLOT_ID = re.compile(r"^MUSE-(\d+)$")
_SQUASH_PR = re.compile(r"\(#(\d+)\)\s*$")
_MERGE_PR = re.compile(r"^Merge pull request #(\d+)\b")
_GITHUB_SLUG = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)")
_SECRET_MARK = re.compile(r"(ghs_|ghp_|github_pat_|x-access-token)", re.I)
_SLOT_MENTION = re.compile(r"(?<![A-Za-z0-9])MUSE-0*\d+(?!\d)")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
_HOME_DIR = frozenset({"home", "users"})
_PROCESS_STAMPS = ("heartbeat_at", "updated_at", "create_time", "started_at", "timestamp", "at")
_HEARTBEAT_FILES = ("heartbeat.json", "process.json")
_JOURNAL_NAME = "coordination_ledger.jsonl"
_BRIDGE_NAME = "ledger_bridge_state.json"
_JOURNAL_STATUS = frozenset({"WORKING", "DONE", "BLOCKED", "ERROR"})
_JOURNAL_EVENT = frozenset({"ASSIGNED", "STARTED", "PARTIAL", "FINAL", "BLOCKED", "ERROR", "CANCELLED"})
_PUBLIC_MERGE = ("pr", "subject", "sha", "source", "at")
FLOWERS = (
    "muse_wall",
    "ledger",
    "ledger_bridge",
    "postfach_alt_an_neu",
    "postfach_neu_an_alt",
    "github_ci",
    "draft_prs",
    "merged_prs",
)
_POSTFACH = {
    "postfach_alt_an_neu": "POSTFACH_ALT_AN_NEU",
    "postfach_neu_an_alt": "POSTFACH_NEU_AN_ALT",
}
_MISSION_FIELDS = ("status", "reason", "task_id")
_merge_cache_lock = threading.Lock()
_merge_cache: dict[str, tuple[str, str, list[dict]]] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def station_key(slot_id: str) -> tuple:
    """Slot number, lowest first. Unnumbered names follow, in byte order."""
    match = _SLOT_ID.fullmatch(slot_id or "")
    if match:
        return (0, int(match.group(1)), slot_id)
    return (1, 10**9, slot_id or "")


def _iso_text(value: str) -> str:
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


def _parse_stamp(value: str) -> Optional[datetime]:
    if not isinstance(value, str) or not value or value == UNAVAILABLE:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fresh(at: str, observed_at: str) -> bool:
    seen = _parse_stamp(at)
    observed = _parse_stamp(observed_at)
    if seen is None or observed is None:
        return False
    delta = (observed - seen).total_seconds()
    return -5 <= delta <= HEARTBEAT_S


def _file_stamp(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        return UNAVAILABLE


def _path_parts(path: Path, root: Path) -> list[str]:
    """Path pieces for a label. Prefer a repo-relative tail and never keep `..`."""
    for base in (root, repo_root()):
        try:
            rel = path.resolve().relative_to(base.resolve()).as_posix()
        except (OSError, ValueError):
            continue
        if rel and not rel.startswith("../"):
            return [part for part in rel.split("/") if part and part not in (".", "..")]
    text = re.sub(r"^[A-Za-z]:", "", str(path).replace("\\", "/"))
    return [part for part in text.split("/") if part and part not in (".", "..")]


def _display_path(path: Path, root: Path) -> str:
    """Short camera label: slot/file or file name.

    Absolute paths, home directories, and the username after home/Users never
    appear. An internal repo prefix is dropped; the slot id is enough.
    """
    parts = _path_parts(path, root)
    # Only a leading /home/<name> or /Users/<name> prefix is an account directory.
    username = None
    if parts and parts[0].lower() in _HOME_DIR and len(parts) > 1:
        username = parts[1]
    if not parts:
        return "source"
    name = parts[-1]
    parent = parts[-2] if len(parts) > 1 else ""
    if not _SAFE_NAME.fullmatch(name) or (username and name == username):
        return "source"
    if _SLOT_ID.fullmatch(parent) and parent != username:
        return f"{parent}/{name}"
    return name


def _unavailable(source: str, observed_at: str) -> dict:
    return {
        "available": False,
        "active": False,
        "source": source,
        "at": UNAVAILABLE,
        "observed_at": observed_at,
        "value": UNAVAILABLE,
    }


def resolve_muse_wall(root: Path) -> tuple[Optional[Path], str]:
    """Explicit wall directory, otherwise the slot directory in this repo.

    A configured directory that is not there stays unavailable.
    """
    configured = os.environ.get("COURIER_MUSE_WALL_DIR") or os.environ.get("COURIER_WALL_DIR")
    if configured:
        path = Path(configured)
        label = "COURIER_MUSE_WALL_DIR" if os.environ.get("COURIER_MUSE_WALL_DIR") else "COURIER_WALL_DIR"
        return (path if path.is_dir() else None), label
    default = root / "scripts" / "windows_muse_wall" / "runtime" / "slots"
    return (default if default.is_dir() else None), "muse wall"


def _slot_token(slot_id: str) -> Optional[re.Pattern[str]]:
    """MUSE-01 and MUSE-1 are one station. MUSE-10 is not MUSE-1."""
    match = _SLOT_ID.fullmatch(slot_id or "")
    if not match:
        return None
    number = str(int(match.group(1)))
    return re.compile(rf"(?<![A-Za-z0-9])MUSE-0*{re.escape(number)}(?!\d)")


def _ref_exists(root: Path, full: str) -> bool:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "show-ref", "--verify", "--quiet", full],
            check=False, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _is_ancestor(root: Path, older: str, newer: str) -> Optional[bool]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", older, newer],
            check=False, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    return None


def _merged_refs(root: Path) -> list[str]:
    """Refs that hold merged history.

    A stale local branch does not hide commits that exist only on origin, and
    a missing local branch still reads origin. Diverged refs are both read.
    """
    local = MERGED_REF
    origin = f"origin/{MERGED_REF}"
    has_local = _ref_exists(root, "refs/heads/integration/v1")
    has_origin = _ref_exists(root, "refs/remotes/origin/integration/v1")
    if has_local and has_origin:
        local_before = _is_ancestor(root, local, origin)
        origin_before = _is_ancestor(root, origin, local)
        if local_before is None or origin_before is None:
            return [local, origin]
        if local_before and origin_before:
            return [local]
        if local_before:
            return [origin]
        if origin_before:
            return [local]
        return [local, origin]
    if has_local:
        return [local]
    if has_origin:
        return [origin]
    return []


def _git_text(root: Path, args: list[str], timeout: int) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False, capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _load_ref_merges(root: Path, ref: str) -> Optional[tuple[str, str, list[dict], str]]:
    source = f"git log {ref}"
    head = _git_text(root, ["log", "-1", "--pretty=format:%H%x1f%cI", ref], 20)
    if not head:
        return None
    head_sha, _, head_at_raw = head.partition("\x1f")
    head_at = _iso_text(head_at_raw.strip())
    head_sha = head_sha.strip()
    if not head_sha or head_at == UNAVAILABLE:
        return None
    cache_key = f"{root.resolve()}|{ref}"
    with _merge_cache_lock:
        cached = _merge_cache.get(cache_key)
    if cached and cached[0] == head_sha:
        return head_sha, head_at, cached[2], source
    log = _git_text(root, ["log", ref, "--pretty=format:%H%x1f%cI%x1f%s%x1f%b%x1e"], 30)
    if log is None:
        return None
    rows = _parse_merges(log, source)
    with _merge_cache_lock:
        _merge_cache[cache_key] = (head_sha, head_at, rows)
    return head_sha, head_at, rows, source


def _union_rows(groups: list[list[dict]]) -> list[dict]:
    found: dict[int, dict] = {}
    for rows in groups:
        for row in rows:
            number = row["pr"]
            current = found.get(number)
            slots = list(row.get("slots") or [])
            if current is None:
                found[number] = {
                    "pr": row["pr"], "subject": row["subject"], "sha": row["sha"],
                    "source": row["source"], "at": row["at"], "slots": slots,
                }
                continue
            for token in slots:
                if token not in current["slots"]:
                    current["slots"].append(token)
            if (row.get("at") or "", row.get("pr") or 0) >= (current.get("at") or "", current.get("pr") or 0):
                kept = current["slots"]
                found[number] = {
                    "pr": row["pr"], "subject": row["subject"], "sha": row["sha"],
                    "source": row["source"], "at": row["at"], "slots": kept,
                }
    return sorted(found.values(), key=lambda row: (row["at"], row["pr"]))


def read_merged_prs(root: Path, observed_at: str) -> dict:
    source = f"git log {MERGED_REF}"
    if not (root / ".git").exists():
        block = _unavailable(source, observed_at)
        block["rows"] = []
        return block
    refs = _merged_refs(root)
    if not refs:
        block = _unavailable(source, observed_at)
        block["rows"] = []
        return block
    loaded = []
    for ref in refs:
        item = _load_ref_merges(root, ref)
        if item is not None:
            loaded.append(item)
    if not loaded:
        block = _unavailable(source, observed_at)
        block["rows"] = []
        return block
    source = " + ".join(item[3] for item in loaded)
    rows = _union_rows([item[2] for item in loaded])
    head_sha, head_at, _rows, _source = max(loaded, key=lambda item: item[1])
    newest = rows[-1]["at"] if rows else head_at
    return {
        "available": True,
        "active": bool(rows) and _fresh(newest, observed_at),
        "source": source,
        "at": head_at,
        "observed_at": observed_at,
        "value": str(len(rows)),
        "head": head_sha,
        "rows": rows,
    }


def _slot_mentions(*parts: str) -> list[str]:
    found = []
    seen = set()
    for part in parts:
        for match in _SLOT_MENTION.finditer(part or ""):
            token = match.group(0)
            if token not in seen:
                seen.add(token)
                found.append(token)
    return found


def _parse_merges(text: str, source: str) -> list[dict]:
    found: dict[int, dict] = {}
    for record in text.split("\x1e"):
        parts = record.strip("\n").split("\x1f")
        if len(parts) < 3:
            continue
        sha, committed_at, subject = parts[0].strip(), parts[1].strip(), parts[2].strip("\n")
        body = parts[3] if len(parts) > 3 else ""
        match = _SQUASH_PR.search(subject) or _MERGE_PR.search(subject)
        if not match:
            continue
        number = int(match.group(1))
        mentions = _slot_mentions(subject, body)
        if number in found:
            for token in mentions:
                if token not in found[number]["slots"]:
                    found[number]["slots"].append(token)
            continue
        found[number] = {
            "pr": number,
            "subject": subject,
            "sha": sha,
            "source": source,
            "at": _iso_text(committed_at.strip()),
            "slots": mentions,
        }
    return sorted(found.values(), key=lambda row: (row["at"], row["pr"]))


def _row_mentions_slot(row: dict, pattern: re.Pattern[str]) -> bool:
    if pattern.search(row.get("subject") or ""):
        return True
    return any(pattern.search(token) for token in row.get("slots") or [])


def _done_for(slot_id: str, merged: dict) -> dict:
    source = merged.get("source") or f"git log {MERGED_REF}"
    if not merged.get("available"):
        return {"value": UNAVAILABLE, "source": source, "at": UNAVAILABLE}
    pattern = _slot_token(slot_id)
    hits = []
    if pattern is not None:
        hits = [row for row in merged.get("rows") or [] if _row_mentions_slot(row, pattern)]
    if hits:
        latest = max(hits, key=lambda row: (row.get("at") or "", row.get("pr") or 0))
        return {
            "value": "DONE",
            "source": latest.get("source") or source,
            "at": latest.get("at") or UNAVAILABLE,
            "pr": latest.get("pr"),
        }
    return {"value": "not done", "source": source, "at": merged.get("at") or UNAVAILABLE}


def _as_stamp(value) -> Optional[str]:
    if isinstance(value, str):
        return _iso_text(value) if _parse_stamp(value) else None
    return _iso_unix(value)


def _mapping_stamp(data: dict) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    for key in _PROCESS_STAMPS:
        if key not in data:
            continue
        found = _as_stamp(data.get(key))
        if found:
            return found
    return None


def _read_object(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _slot_heartbeat(slot_dir: Path, data: dict, observed_at: str) -> tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """A fresh process timestamp is a live heartbeat.

    Checked-in slot files say READY with process null. That state is not a heartbeat.
    """
    for name in _HEARTBEAT_FILES:
        hb_path = slot_dir / name
        if not hb_path.is_file():
            continue
        recorded = _read_object(hb_path)
        if recorded is None:
            continue
        process = recorded.get("process") if isinstance(recorded.get("process"), dict) else None
        stamp = _mapping_stamp(process) if process is not None else None
        stamp = stamp or _mapping_stamp(recorded)
        if not stamp or not _fresh(stamp, observed_at):
            continue
        hb_state = recorded.get("state") if isinstance(recorded.get("state"), str) else None
        cleaned = hb_state.strip()[:80] if hb_state and hb_state.strip() else None
        return True, stamp, cleaned, name
    process = data.get("process")
    if not isinstance(process, dict):
        return False, None, None, None
    stamp = _mapping_stamp(process) or _as_stamp(data.get("updated_at"))
    if stamp and _fresh(stamp, observed_at):
        return True, stamp, None, None
    return False, None, None, None


def read_muse_wall(root: Path, wall: Optional[Path], label: str, observed_at: str, merged: dict) -> dict:
    if wall is None or not wall.is_dir():
        block = _unavailable(label, observed_at)
        block["stations"] = []
        return block
    stations = []
    for path in sorted(wall.glob("*/state.json")):
        rel = _display_path(path, root)
        slot_id = path.parent.name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            stations.append({
                "id": slot_id,
                "heartbeat": False,
                "state": {"value": UNAVAILABLE, "source": rel, "at": UNAVAILABLE},
                "process": {"value": UNAVAILABLE, "source": rel, "at": UNAVAILABLE},
                "done": _done_for(slot_id, merged),
            })
            continue
        if not isinstance(data, dict):
            data = {}
        recorded_id = data.get("slot_id")
        if isinstance(recorded_id, str) and recorded_id.strip():
            slot_id = recorded_id.strip()
        slot_at = _as_stamp(data.get("updated_at")) or UNAVAILABLE
        live, live_at, live_state, live_name = _slot_heartbeat(path.parent, data, observed_at)
        recorded_state = data.get("state")
        state_source = rel
        state_at = slot_at
        if live and live_state:
            state_value = live_state
            state_at = live_at or UNAVAILABLE
            state_source = _display_path(path.parent / live_name, root) if live_name else rel
        elif live and isinstance(recorded_state, str) and recorded_state.strip() and _fresh(slot_at, observed_at):
            state_value = recorded_state.strip()[:80]
        elif live:
            state_value = UNAVAILABLE
            state_at = live_at or UNAVAILABLE
            if live_name:
                state_source = _display_path(path.parent / live_name, root)
        else:
            state_value = PAUSE
        process = data.get("process")
        if "process" not in data:
            process_value = UNAVAILABLE
        elif process is None:
            process_value = "none"
        else:
            process_value = "present"
        stations.append({
            "id": slot_id,
            "heartbeat": live,
            "state": {"value": state_value, "source": state_source, "at": state_at},
            "process": {"value": process_value, "source": rel, "at": slot_at},
            "done": _done_for(slot_id, merged),
        })
    stations.sort(key=lambda station: station_key(station["id"]))
    live_count = sum(1 for station in stations if station["heartbeat"])
    times = [station["state"]["at"] for station in stations if station["state"]["at"] != UNAVAILABLE]
    return {
        "available": True,
        "active": live_count > 0,
        "source": label,
        "at": max(times) if times else UNAVAILABLE,
        "observed_at": observed_at,
        "value": str(live_count) if live_count else PAUSE,
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
        "active": len(items) > 0,
        "source": source,
        "at": read_at,
        "observed_at": observed_at,
        "value": str(len(items)),
        "counts": safe_counts,
        "done_shown": shown if isinstance(shown, int) and not isinstance(shown, bool) else UNAVAILABLE,
        "items": items,
    }


def _bridge_state_rows(path: Optional[Path], root: Path) -> tuple[list[dict], bool, str]:
    """Rows from ledger_bridge_state.json. The bool is False when the file is absent or unreadable."""
    if path is None or not path.is_file():
        return [], False, UNAVAILABLE
    file_at = _file_stamp(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [], False, file_at
    missions = data.get("missions") if isinstance(data, dict) else None
    if not isinstance(missions, dict):
        return [], False, file_at
    rel = _display_path(path, root)
    listed = []
    for mission_id in sorted(missions):
        mapping = missions[mission_id]
        if not isinstance(mission_id, str) or not isinstance(mapping, dict):
            continue
        recorded_at = mapping.get("updated_at") if isinstance(mapping.get("updated_at"), str) else ""
        at = _iso_text(recorded_at) if recorded_at and _parse_stamp(recorded_at) else file_at
        status = mapping.get("status") if isinstance(mapping.get("status"), str) and mapping.get("status").strip() else UNAVAILABLE
        row = {"id": mission_id, "status": status, "source": rel, "at": at}
        for key in _MISSION_FIELDS:
            if key == "status":
                continue
            value = mapping.get(key)
            if isinstance(value, str) and value.strip() and not _SECRET_MARK.search(value):
                row[key] = value.strip()[:120]
        listed.append(row)
    return listed, True, file_at


def _journal_rows(path: Path, root: Path) -> list[dict]:
    """Latest recorded coordination-ledger event per mission. Lines that are not events are skipped."""
    latest: dict[str, tuple[str, int, dict]] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return []
    rel = _display_path(path, root)
    for index, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        mission_id = record.get("mission_id")
        status = record.get("status")
        created = record.get("created_at")
        event_type = record.get("event_type")
        if not isinstance(mission_id, str) or not mission_id.strip():
            continue
        if not isinstance(status, str) or status not in _JOURNAL_STATUS:
            continue
        if not isinstance(created, str) or _parse_stamp(created) is None:
            continue
        if event_type is not None and (not isinstance(event_type, str) or event_type not in _JOURNAL_EVENT):
            continue
        at = _iso_text(created)
        previous = latest.get(mission_id)
        if previous is not None and (previous[0], previous[1]) > (at, index):
            continue
        row = {"id": mission_id.strip()[:120], "status": status, "source": rel, "at": at}
        if isinstance(event_type, str):
            row["event_type"] = event_type
        latest[mission_id] = (at, index, row)
    return [item[2] for item in sorted(latest.values(), key=lambda item: item[2]["id"])]


def read_ledger_bridge(home: Optional[Path], root: Path, observed_at: str) -> dict:
    source = _BRIDGE_NAME
    state_path = (home / _BRIDGE_NAME) if home is not None else None
    journal_path = (home / _JOURNAL_NAME) if home is not None else None
    journal_ok = journal_path is not None and journal_path.is_file()
    listed, state_ok, state_at = _bridge_state_rows(state_path, root)
    if not state_ok and not journal_ok:
        block = _unavailable(source, observed_at)
        block["missions"] = []
        return block
    seen = {row["id"] for row in listed}
    if journal_ok:
        journal_rows = _journal_rows(journal_path, root)
        by_id = {row["id"]: row for row in journal_rows}
        for row in listed:
            extra = by_id.get(row["id"])
            if extra is None or row.get("status") != UNAVAILABLE:
                continue
            row["status"] = extra["status"]
            row["status_source"] = extra["source"]
            row["status_at"] = extra["at"]
            if extra.get("event_type"):
                row["event_type"] = extra["event_type"]
        for row in journal_rows:
            if row["id"] in seen:
                continue
            listed.append(row)
            seen.add(row["id"])
        listed.sort(key=lambda row: row["id"])
    if state_ok:
        block_source = source
        block_at = state_at
    else:
        block_source = _JOURNAL_NAME
        times = [row["at"] for row in listed if row["at"] != UNAVAILABLE]
        block_at = max(times) if times else _file_stamp(journal_path)
    return {
        "available": True,
        "active": len(listed) > 0,
        "source": block_source,
        "at": block_at,
        "observed_at": observed_at,
        "value": str(len(listed)),
        "missions": listed,
    }


def _postfach_candidates(name: str, home: Optional[Path], root: Path) -> list[Path]:
    names = (name, f"{name}.json")
    roots = []
    configured = os.environ.get("COURIER_POSTFACH_DIR")
    if configured:
        roots.append(Path(configured))
    if home is not None:
        roots.append(home)
        roots.append(home / "postfach")
    roots.append(root)
    found = []
    for base in roots:
        for leaf in names:
            found.append(base / leaf)
    return found


def _entry_count(payload) -> Optional[int]:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("messages", "items"):
            if isinstance(payload.get(key), list):
                return len(payload[key])
        return 1 if payload else 0
    if isinstance(payload, str):
        return 1 if payload.strip() else 0
    return None


def read_postfach(flower: str, home: Optional[Path], root: Path, observed_at: str) -> dict:
    name = _POSTFACH[flower]
    chosen = next((path for path in _postfach_candidates(name, home, root) if path.is_file()), None)
    if chosen is None:
        block = _unavailable(name, observed_at)
        block["entries"] = None
        return block
    try:
        text = chosen.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        block = _unavailable(name, observed_at)
        block["entries"] = None
        return block
    try:
        payload = json.loads(text) if text.strip() else []
    except json.JSONDecodeError:
        payload = text
    count = _entry_count(payload)
    if count is None:
        block = _unavailable(name, observed_at)
        block["entries"] = None
        return block
    return {
        "available": True,
        "active": count > 0,
        "source": name,
        "at": _file_stamp(chosen),
        "observed_at": observed_at,
        "value": str(count),
        "entries": count,
    }


def _github_slug(root: Path) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            check=True, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    cleaned = re.sub(r"//[^/@\s]+@", "//", proc.stdout.strip())
    match = _GITHUB_SLUG.search(cleaned)
    if not match:
        return None
    return f"{match.group('owner')}/{match.group('repo')}"


def _github_get(path: str) -> Optional[object]:
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if token:
        request = urllib.request.Request(
            "https://api.github.com" + path,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "courier-kolibri",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, urllib.error.URLError, ValueError):
            return None
    try:
        proc = subprocess.run(
            ["gh", "api", path], check=False, capture_output=True, text=True, timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def read_github(root: Path, observed_at: str, fetch=None) -> tuple[dict, dict]:
    """CI status of integration/v1, and open draft pull requests into that branch."""
    ci_source = f"github statuses {MERGED_REF}"
    pr_source = f"github pulls {MERGED_REF}"
    slug = _github_slug(root)
    if not slug:
        ci = _unavailable(ci_source, observed_at)
        drafts = _unavailable(pr_source, observed_at)
        ci["checks"] = []
        drafts["rows"] = []
        return ci, drafts
    getter = fetch if fetch is not None else _github_get
    status = getter(f"/repos/{slug}/commits/{MERGED_REF}/status")
    pulls = getter(f"/repos/{slug}/pulls?state=open&base={MERGED_REF}&per_page=100")
    ci = _read_ci(status, ci_source, observed_at)
    drafts = _read_drafts(pulls, pr_source, observed_at)
    return ci, drafts


def _read_ci(status, source: str, observed_at: str) -> dict:
    if not isinstance(status, dict) or not isinstance(status.get("state"), str):
        block = _unavailable(source, observed_at)
        block["checks"] = []
        return block
    checks = []
    for row in status.get("statuses") or []:
        if not isinstance(row, dict):
            continue
        context = row.get("context") if isinstance(row.get("context"), str) else UNAVAILABLE
        state = row.get("state") if isinstance(row.get("state"), str) else UNAVAILABLE
        at = _iso_text(row["updated_at"]) if isinstance(row.get("updated_at"), str) else UNAVAILABLE
        checks.append({"context": context, "state": state, "source": source, "at": at})
    checks.sort(key=lambda row: (row["context"], row["at"]))
    times = [row["at"] for row in checks if row["at"] != UNAVAILABLE]
    return {
        "available": True,
        "active": any(_fresh(row["at"], observed_at) for row in checks),
        "source": source,
        "at": max(times) if times else UNAVAILABLE,
        "observed_at": observed_at,
        "value": status["state"],
        "sha": status.get("sha") if isinstance(status.get("sha"), str) else UNAVAILABLE,
        "checks": checks,
    }


def _read_drafts(pulls, source: str, observed_at: str) -> dict:
    if not isinstance(pulls, list):
        block = _unavailable(source, observed_at)
        block["rows"] = []
        return block
    rows = []
    for pull in pulls:
        if not isinstance(pull, dict) or pull.get("draft") is not True:
            continue
        number = pull.get("number")
        if isinstance(number, bool) or not isinstance(number, int):
            continue
        title = pull.get("title") if isinstance(pull.get("title"), str) and pull.get("title").strip() else UNAVAILABLE
        at = _iso_text(pull["updated_at"]) if isinstance(pull.get("updated_at"), str) else UNAVAILABLE
        rows.append({"pr": number, "title": title, "source": source, "at": at})
    rows.sort(key=lambda row: row["pr"])
    times = [row["at"] for row in rows if row["at"] != UNAVAILABLE]
    return {
        "available": True,
        "active": len(rows) > 0,
        "source": source,
        "at": max(times) if times else UNAVAILABLE,
        "observed_at": observed_at,
        "value": str(len(rows)),
        "rows": rows,
    }


def build_snapshot(hub, *, root: Optional[Path] = None, wall: Optional[Path] = None,
                   wall_label: Optional[str] = None, observed_at: Optional[str] = None,
                   github_fetch=None) -> dict:
    """Assemble one snapshot. Each reader fails on its own."""
    root = root or repo_root()
    observed_at = observed_at or utc_now()
    home = getattr(hub, "home", None)
    if wall is None and wall_label is None:
        wall, wall_label = resolve_muse_wall(root)
    elif wall_label is None:
        wall_label = _display_path(wall, root) if wall is not None else "muse wall"
    try:
        merged = read_merged_prs(root, observed_at)
    except Exception:  # noqa: BLE001
        merged = _unavailable(f"git log {MERGED_REF}", observed_at)
        merged["rows"] = []
    try:
        muse = read_muse_wall(root, wall, wall_label or "muse wall", observed_at, merged)
    except Exception:  # noqa: BLE001
        muse = _unavailable(wall_label or "muse wall", observed_at)
        muse["stations"] = []
    try:
        ledger_view = hub.home_view() if hub is not None else None
        ledger = read_ledger(ledger_view, observed_at)
    except Exception:  # noqa: BLE001
        ledger = _unavailable("courier journal (courier.db)", observed_at)
        ledger["items"] = []
        ledger["counts"] = {}
    try:
        bridge = read_ledger_bridge(home, root, observed_at)
    except Exception:  # noqa: BLE001
        bridge = _unavailable("ledger_bridge_state.json", observed_at)
        bridge["missions"] = []
    postfach = {}
    for flower in ("postfach_alt_an_neu", "postfach_neu_an_alt"):
        try:
            postfach[flower] = read_postfach(flower, home, root, observed_at)
        except Exception:  # noqa: BLE001
            postfach[flower] = _unavailable(_POSTFACH[flower], observed_at)
            postfach[flower]["entries"] = None
    try:
        github_ci, draft_prs = read_github(root, observed_at, fetch=github_fetch)
    except Exception:  # noqa: BLE001
        github_ci = _unavailable(f"github statuses {MERGED_REF}", observed_at)
        github_ci["checks"] = []
        draft_prs = _unavailable(f"github pulls {MERGED_REF}", observed_at)
        draft_prs["rows"] = []
    snapshot = {
        "observed_at": observed_at,
        "muse_wall": muse,
        "ledger": ledger,
        "ledger_bridge": bridge,
        "github_ci": github_ci,
        "draft_prs": draft_prs,
        "merged_prs": _public_merges(merged),
        **postfach,
    }
    flying = [name for name in FLOWERS if snapshot[name].get("active") is True]
    snapshot["bird"] = {"state": "fly" if flying else "rest", "target": flying[0] if flying else None}
    snapshot["activity"] = None if flying else REST_TEXT
    return snapshot


def _public_merges(merged: dict) -> dict:
    shown = dict(merged)
    shown["rows"] = [
        {key: row[key] for key in _PUBLIC_MERGE if key in row}
        for row in merged.get("rows") or []
        if isinstance(row, dict)
    ]
    return shown


def snapshot_for_hub(hub) -> dict:
    return build_snapshot(hub)
