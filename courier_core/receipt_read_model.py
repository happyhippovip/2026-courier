"""Read-only receipts over the ledger bridge state and verified controller results.

The bridge file is ``<home>/ledger_bridge_state.json``. Missions are a map of
mission id to the #267 fields, or a list of those objects. Verified results are
``RESULT_ACCEPTED`` rows in ``<home>/courier.db``. This module does not import
the bridge, the controller, or the goal contract. It does not write either file.

A missing file is empty. A file that is not the expected shape, is larger than
1 MiB, or cannot be read is ``UNREADABLE``. Callers get a document. They do not
get an exception or a path.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MAX_FILE_BYTES = 1024 * 1024
BRIDGE_NAME = "ledger_bridge_state.json"
RESULTS_NAME = "courier.db"
KNOWN_STATUSES = ("BLOCKED", "ERROR", "FINAL_DONE", "POSTED")
RECEIPT_FIELDS = (
    "accepted_result_id",
    "claim_event_id",
    "evidence_ref",
    "goal_id",
    "mission_id",
    "reason",
    "result",
    "status",
    "task_id",
    "updated_at",
)
RESULT_FIELDS = ("attempt", "dispatch_id", "outcome", "result_id", "task_id", "ts_utc")
_ACCEPTED = "RESULT_ACCEPTED"
_OPTIONAL = (
    "accepted_result_id",
    "claim_event_id",
    "evidence_ref",
    "goal_id",
    "reason",
    "status",
    "updated_at",
)


class ReceiptReadModel:
    """One home directory. Every method re-reads. None of them write."""

    def __init__(self, home):
        self.home = Path(home)

    def list_receipts(self, status=None, goal_id=None, since=None, until=None) -> dict:
        """Receipts for a hub list. ``since`` and ``until`` are inclusive UTC instants."""
        bridge, results, receipts = self._load()
        document = _envelope(bridge, results, receipts)
        if not document["readable"]:
            document["receipts"] = []
            return document
        start = _parse_time(since) if since is not None else None
        end = _parse_time(until) if until is not None else None
        if (since is not None and start is None) or (until is not None and end is None):
            document["receipts"] = []
            document["filter"] = "INVALID"
            return document
        selected = []
        for receipt in receipts:
            if status is not None and receipt["status"] != status:
                continue
            if goal_id is not None and receipt["goal_id"] != goal_id:
                continue
            if start is not None or end is not None:
                moment = _parse_time(receipt["updated_at"])
                if moment is None or (start is not None and moment < start) or (end is not None and moment > end):
                    continue
            selected.append(receipt)
        document["receipts"] = selected
        return document

    def receipt(self, task_id) -> dict:
        """One receipt by controller task id, or ``found`` false."""
        bridge, results, receipts = self._load()
        document = _envelope(bridge, results, receipts)
        document["task_id"] = task_id if isinstance(task_id, str) else None
        document["found"] = False
        document["receipt"] = None
        if not document["readable"] or not isinstance(task_id, str):
            return document
        matches = [item for item in receipts if item["task_id"] == task_id]
        if len(matches) == 1:
            document["found"] = True
            document["receipt"] = matches[0]
        return document

    def summary(self) -> dict:
        """Counts per status and the latest ``updated_at``. Unreadable input counts as empty."""
        bridge, results, receipts = self._load()
        document = _envelope(bridge, results, receipts)
        counts = {name: 0 for name in (*KNOWN_STATUSES, "UNSET")}
        latest = None
        latest_raw = None
        if document["readable"]:
            for item in receipts:
                status = item["status"]
                if status is None:
                    counts["UNSET"] += 1
                elif status in counts:
                    counts[status] += 1
                else:
                    counts[status] = counts.get(status, 0) + 1
                moment = _parse_time(item["updated_at"])
                if moment is not None and (latest is None or moment > latest):
                    latest = moment
                    latest_raw = item["updated_at"]
        document["counts"] = counts
        document["total"] = len(receipts) if document["readable"] else 0
        document["last_updated"] = latest_raw
        return document

    def _load(self):
        bridge, missions = _read_bridge(self.home / BRIDGE_NAME)
        results_state, results = _read_results(self.home / RESULTS_NAME)
        if bridge == "UNREADABLE" or results_state == "UNREADABLE" or missions is None:
            if missions is None and bridge == "OK":
                bridge = "UNREADABLE"
            return bridge, results_state, []
        joined = []
        seen = set()
        for mission_id, mapping in missions:
            task_id = mapping["task_id"]
            if task_id in seen:
                return "UNREADABLE", results_state, []
            seen.add(task_id)
            result = None
            accepted = mapping.get("accepted_result_id")
            if isinstance(accepted, str) and accepted:
                result = results.get((task_id, accepted))
            joined.append(_receipt(mission_id, mapping, result))
        joined.sort(key=_sort_key)
        return bridge, results_state, joined


def _envelope(bridge, results, receipts) -> dict:
    readable = bridge != "UNREADABLE" and results != "UNREADABLE"
    return {
        "readable": readable,
        "bridge": bridge,
        "results": results,
        "receipts": list(receipts) if readable else [],
    }


def _receipt(mission_id, mapping, result) -> dict:
    body = {
        "accepted_result_id": _optional(mapping, "accepted_result_id"),
        "claim_event_id": _optional(mapping, "claim_event_id"),
        "evidence_ref": _optional(mapping, "evidence_ref"),
        "goal_id": _optional(mapping, "goal_id"),
        "mission_id": mission_id,
        "reason": _optional(mapping, "reason"),
        "result": result,
        "status": _optional(mapping, "status"),
        "task_id": mapping["task_id"],
        "updated_at": _optional(mapping, "updated_at"),
    }
    return {key: body[key] for key in RECEIPT_FIELDS}


def _optional(mapping, name):
    if name not in mapping or mapping[name] is None:
        return None
    return mapping[name]


def _read_bridge(path: Path):
    state, raw = _read_capped(path)
    if state != "OK":
        return state, [] if state == "ABSENT" else None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return "UNREADABLE", None
    missions = _missions(data)
    if missions is None:
        return "UNREADABLE", None
    return "OK", missions


def _missions(data):
    if not isinstance(data, dict) or set(data) != {"missions"}:
        return None
    missions = data["missions"]
    if isinstance(missions, dict):
        rows = []
        for mission_id, mapping in missions.items():
            parsed = _mapping(mapping)
            if not isinstance(mission_id, str) or not mission_id or parsed is None:
                return None
            if "mission_id" in mapping and mapping["mission_id"] != mission_id:
                return None
            rows.append((mission_id, parsed))
        return rows
    if isinstance(missions, list):
        rows = []
        for mapping in missions:
            parsed = _mapping(mapping)
            if parsed is None or not isinstance(mapping.get("mission_id"), str) or not mapping["mission_id"]:
                return None
            rows.append((mapping["mission_id"], parsed))
        return rows
    return None


def _mapping(mapping):
    if not isinstance(mapping, dict):
        return None
    task_id = mapping.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return None
    for name in _OPTIONAL:
        if name in mapping and mapping[name] is not None and not isinstance(mapping[name], str):
            return None
    return mapping


def _read_results(path: Path):
    state, _raw = _read_capped(path)
    if state != "OK":
        return state, {}
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        return "UNREADABLE", {}
    try:
        conn.execute("PRAGMA query_only=ON")
        try:
            rows = conn.execute(
                "SELECT task_id, result_id, attempt, dispatch_id, ts_utc, payload "
                "FROM events WHERE type = ?",
                (_ACCEPTED,),
            ).fetchall()
        except sqlite3.Error:
            return "UNREADABLE", {}
    finally:
        conn.close()
    found = {}
    for task_id, result_id, attempt, dispatch_id, ts_utc, payload in rows:
        if not isinstance(task_id, str) or not task_id or not isinstance(result_id, str) or not result_id:
            continue
        record = {
            "attempt": attempt if isinstance(attempt, int) and not isinstance(attempt, bool) else None,
            "dispatch_id": dispatch_id if isinstance(dispatch_id, str) else None,
            "outcome": _outcome(payload),
            "result_id": result_id,
            "task_id": task_id,
            "ts_utc": ts_utc if isinstance(ts_utc, str) else None,
        }
        found[(task_id, result_id)] = {key: record[key] for key in RESULT_FIELDS}
    return "OK", found


def _outcome(payload):
    if not isinstance(payload, str):
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    outcome = data.get("outcome")
    if not isinstance(outcome, str) or not outcome or len(outcome) > 64 or any(ch in outcome for ch in "\n\r"):
        return None
    return outcome


def _read_capped(path: Path):
    try:
        if not path.exists():
            return "ABSENT", None
        if not path.is_file():
            return "UNREADABLE", None
        size = path.stat().st_size
    except OSError:
        return "UNREADABLE", None
    if isinstance(size, bool) or not isinstance(size, int) or size < 0 or size > MAX_FILE_BYTES:
        return "UNREADABLE", None
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
    except OSError:
        return "UNREADABLE", None
    if len(raw) > MAX_FILE_BYTES:
        return "UNREADABLE", None
    return "OK", raw


def _parse_time(value):
    if not isinstance(value, str) or not value.endswith("Z") or "\n" in value or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _sort_key(receipt):
    moment = _parse_time(receipt["updated_at"])
    stamp = moment.timestamp() if moment is not None else float("inf")
    return (stamp, receipt["task_id"], receipt["mission_id"])
