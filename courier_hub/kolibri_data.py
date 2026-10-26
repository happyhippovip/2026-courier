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
_MISSION_FIELDS = ("status", "reason", "task_id", "workkey", "owner", "lease", "blocker", "resource_pause")
_merge_cache_lock = threading.Lock()
_merge_cache: dict[str, tuple[str, str, list[dict]]] = {}
_github_api_cache: dict[str, tuple[float, Optional[object]]] = {}


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


def _display_path(path: Path, root: Path) -> str:
    for base in (root, repo_root()):
        try:
            return path.resolve().relative_to(base.resolve()).as_posix()
        except (OSError, ValueError):
            continue
    return f"{path.parent.name}/{path.name}"


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
        if (path / "slots").is_dir():
            return path / "slots", label
        return (path if path.is_dir() else None), label
    default = root / "scripts" / "windows_muse_wall" / "runtime" / "slots"
    label = "scripts/windows_muse_wall/runtime/slots"
    return (default if default.is_dir() else None), label


def _slot_token(slot_id: str) -> Optional[re.Pattern[str]]:
    if not _SLOT_ID.fullmatch(slot_id or ""):
        return None
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(slot_id)}(?!\d)")


def _resolve_merged_ref(root: Path) -> Optional[str]:
    """Local integration/v1, then the origin tracking ref, otherwise nothing to read."""
    for full, short in (
        ("refs/heads/integration/v1", MERGED_REF),
        ("refs/remotes/origin/integration/v1", f"origin/{MERGED_REF}"),
    ):
        try:
            proc = subprocess.run(
                ["git", "-C", str(root), "show-ref", "--verify", "--quiet", full],
                check=False, capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode == 0:
            return short
    return None


def read_merged_prs(root: Path, observed_at: str) -> dict:
    source = f"git log {MERGED_REF}"
    if not (root / ".git").exists():
        block = _unavailable(source, observed_at)
        block["rows"] = []
        return block
    ref = _resolve_merged_ref(root)
    if ref is None:
        block = _unavailable(source, observed_at)
        block["rows"] = []
        return block
    source = f"git log {ref}"
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--pretty=format:%H%x1f%cI", ref],
            check=True, capture_output=True, text=True, timeout=20,
        )
        head_sha, _, head_at = head.stdout.partition("\x1f")
        head_at = _iso_text(head_at.strip())
        if not head_sha or head_at == UNAVAILABLE:
            block = _unavailable(source, observed_at)
            block["rows"] = []
            return block
        cache_key = f"{root.resolve()}|{ref}"
        with _merge_cache_lock:
            cached = _merge_cache.get(cache_key)
        if cached and cached[0] == head_sha:
            rows = cached[2]
        else:
            log = subprocess.run(
                ["git", "-C", str(root), "log", ref, "--pretty=format:%H%x1f%cI%x1f%s"],
                check=True, capture_output=True, text=True, timeout=30,
            )
            rows = _parse_merges(log.stdout, source)
            with _merge_cache_lock:
                _merge_cache[cache_key] = (head_sha, head_at, rows)
    except (OSError, subprocess.SubprocessError):
        block = _unavailable(source, observed_at)
        block["rows"] = []
        return block
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
            continue
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
        return {"value": "DONE", "source": source, "at": latest.get("at") or UNAVAILABLE, "pr": latest.get("pr")}
    return {"value": "not done", "source": source, "at": merged.get("at") or UNAVAILABLE}


def _live_heartbeat(data: dict, observed_at: str) -> bool:
    if data.get("process") is None:
        return False
    at = _iso_unix(data.get("updated_at"))
    return bool(at) and _fresh(at, observed_at)


def read_muse_wall(root: Path, wall: Optional[Path], label: str, observed_at: str, merged: dict) -> dict:
    if wall is None or wall.is_symlink() or wall.parent.is_symlink() or not wall.is_dir():
        block = _unavailable(label, observed_at)
        block["stations"] = []
        return block
    stations = []
    for path in sorted(wall.glob("*/state.json")):
        if path.is_symlink() or path.parent.is_symlink():
            continue
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
        at = _iso_unix(data.get("updated_at")) or UNAVAILABLE
        live = _live_heartbeat(data, observed_at)
        recorded_state = data.get("state")
        if live and isinstance(recorded_state, str) and recorded_state.strip():
            state_value = recorded_state.strip()[:80]
        elif live:
            state_value = UNAVAILABLE
        else:
            state_value = PAUSE
        process = data.get("process")
        if "process" not in data:
            process_value = UNAVAILABLE
        elif process is None:
            process_value = "none"
        else:
            process_value = "present"
        station_entry = {
            "id": slot_id,
            "heartbeat": live,
            "state": {"value": state_value, "source": rel, "at": at},
            "process": {"value": process_value, "source": rel, "at": at},
            "done": _done_for(slot_id, merged),
        }
        for opt_key in ("workkey", "owner", "lease"):
            raw_val = data.get(opt_key)
            if live and isinstance(raw_val, str) and raw_val.strip() and not _SECRET_MARK.search(raw_val):
                station_entry[opt_key] = {"value": raw_val.strip()[:80], "source": rel, "at": at}
        for alert_key in ("blocker", "resource_pause"):
            raw_alert = data.get(alert_key)
            if isinstance(raw_alert, bool) and raw_alert:
                station_entry[alert_key] = {"value": "RESOURCE_PAUSE" if alert_key == "resource_pause" else "BLOCKED", "source": rel, "at": at}
            elif isinstance(raw_alert, str) and raw_alert.strip() and not _SECRET_MARK.search(raw_alert):
                station_entry[alert_key] = {"value": raw_alert.strip()[:80], "source": rel, "at": at}
        stations.append(station_entry)
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
            item = {"id": task_id, "title": title, "pile": pile, "source": source, "at": at}
            # Verifier evidence only: the card must say "verified" (resolution
            # verified) AND carry the journaled RESULT_ACCEPTED proof. The event id
            # is that journal event, never derived from the task id; without a
            # proof the item stays unverified.
            proof = card.get("proof") if isinstance(card.get("proof"), dict) else {}
            seq = proof.get("seq")
            if (pile == "done" and card.get("outcome") == "verified" and task_id != UNAVAILABLE
                    and proof.get("event") == "RESULT_ACCEPTED" and isinstance(seq, int)
                    and not isinstance(seq, bool) and seq >= 1
                    and isinstance(proof.get("result_id"), str) and proof.get("result_id")):
                item["verified"] = True
                item["event_id"] = f"journal:{seq}:RESULT_ACCEPTED"
            items.append(item)
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


def read_ledger_bridge(home: Optional[Path], root: Path, observed_at: str) -> dict:
    source = "ledger_bridge_state.json"
    path = (home / "ledger_bridge_state.json") if home is not None else None
    if (path is None or path.is_symlink() or path.parent.is_symlink()
            or path.parent.parent.is_symlink() or not path.is_file()):
        block = _unavailable(source, observed_at)
        block["missions"] = []
        return block
    file_at = _file_stamp(path)
    rel = _display_path(path, root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        block = _unavailable(source, observed_at)
        block["missions"] = []
        return block
    missions = data.get("missions") if isinstance(data, dict) else None
    if not isinstance(missions, dict):
        block = _unavailable(source, observed_at)
        block["missions"] = []
        return block
    listed = []
    for mission_id in sorted(missions):
        mapping = missions[mission_id]
        if not isinstance(mapping, dict):
            continue
        at = mapping.get("updated_at") if isinstance(mapping.get("updated_at"), str) else file_at
        status = mapping.get("status") if isinstance(mapping.get("status"), str) else UNAVAILABLE
        row = {"id": mission_id, "status": status, "source": rel, "at": _iso_text(at) if at != file_at else file_at}
        for key in _MISSION_FIELDS:
            if key == "status":
                continue
            value = mapping.get(key)
            if isinstance(value, str) and value.strip() and not _SECRET_MARK.search(value):
                row[key] = value.strip()[:120]
        listed.append(row)
    return {
        "available": True,
        "active": len(listed) > 0,
        "source": source,
        "at": file_at,
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
    if home is not None and (home.is_symlink() or home.parent.is_symlink()):
        home = None
    chosen = next(
        (
            path for path in _postfach_candidates(name, home, root)
            if not path.is_symlink() and not path.parent.is_symlink() and path.is_file()
        ),
        None,
    )
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
    now_mono = threading.current_thread()  # keep import-free monotonic via datetime
    now_ts = datetime.now(timezone.utc).timestamp()
    with _merge_cache_lock:
        cached = _github_api_cache.get(path)
        if cached is not None and (now_ts - cached[0]) <= 15.0:
            return cached[1]
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    result = None
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
            with urllib.request.urlopen(request, timeout=3) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, urllib.error.URLError, ValueError):
            result = None
    else:
        try:
            proc = subprocess.run(
                ["gh", "api", path], check=False, capture_output=True, text=True, timeout=3,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                result = json.loads(proc.stdout)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            result = None
    with _merge_cache_lock:
        _github_api_cache[path] = (now_ts, result)
    return result


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


def read_arbitrage_research(root: Path, observed_at: str) -> dict:
    """Read-only aggregation of simulated AI arbitrage opportunities & verified revenue.
    
    Invariants:
    - REAL_TRADES=0, WALLET_SIGNING=NO.
    - Simulated profits and verified actual revenue are strictly separated.
    - Missing metrics render as UNAVAILABLE (fail-closed).
    """
    arbi_file = root / "registries" / "arbitrage_research.json"
    if (root.is_symlink() or root.parent.is_symlink()
            or arbi_file.is_symlink() or arbi_file.parent.is_symlink()
            or not arbi_file.is_file()):
        # No research file, no numbers: a missing source stays UNKNOWN.
        res = _unavailable("registries/arbitrage_research.json", observed_at)
        res["pairs_monitored"] = []
        res["simulation"] = {}
        res["verified_actual_revenue"] = {"status": UNAVAILABLE}  # no amount: 0.00 would assert a value nobody knows
        return res

    try:
        data = json.loads(arbi_file.read_text(encoding="utf-8"))
        return {
            "available": True,
            "source": str(arbi_file.name),
            "at": data.get("at", observed_at),
            "title": data.get("title", "👑 COURIER AI ARBITRAGE · BINANCE ↔ KRAKEN"),
            "pairs_monitored": data.get("pairs_monitored", []),
            "simulation": data.get("simulation", {}),
            "verified_actual_revenue": data.get("verified_actual_revenue", {"status": "UNKNOWN"}),
        }
    except Exception:  # noqa: BLE001
        res = _unavailable("registries/arbitrage_research.json", observed_at)
        res["pairs_monitored"] = []
        res["simulation"] = {}
        res["verified_actual_revenue"] = {"status": UNAVAILABLE}  # no amount: 0.00 would assert a value nobody knows
        return res


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
    try:
        arbi = read_arbitrage_research(root, observed_at)
    except Exception:  # noqa: BLE001
        arbi = _unavailable("arbitrage_research", observed_at)
        arbi["pairs_monitored"] = []
        arbi["simulation"] = {}
        arbi["verified_actual_revenue"] = {"status": UNAVAILABLE}  # no amount: 0.00 would assert a value nobody knows

    snapshot = {
        "observed_at": observed_at,
        "arbitrage_research": arbi,
        "muse_wall": muse,
        "ledger": ledger,
        "ledger_bridge": bridge,
        "github_ci": github_ci,
        "draft_prs": draft_prs,
        "merged_prs": merged,
        **postfach,
    }
    flying = [name for name in FLOWERS if snapshot[name].get("active") is True]
    snapshot["bird"] = {"state": "fly" if flying else "rest", "target": flying[0] if flying else None}
    snapshot["activity"] = None if flying else REST_TEXT
    return snapshot


def snapshot_for_hub(hub) -> dict:
    return build_snapshot(
        hub,
        root=getattr(hub, "kolibri_root", None),
        wall=getattr(hub, "kolibri_wall", None),
        wall_label=getattr(hub, "kolibri_wall_label", None),
        github_fetch=getattr(hub, "github_fetch", None),
    )
