"""Fail-closed reader for ``<state_dir>/ledger_bridge_state.json``.

The file is the mission map written by the ledger-to-V1 bridge:
``{"missions": {mission_id: mapping}}`` or ``{"missions": [mapping, ...]}``
where every mapping carries a non-empty string ``task_id``. Optional fields
(``status``, ``reason``, ``goal_id``, ``updated_at``, ``accepted_result_id``,
``claim_event_id``, ``evidence_ref``) are strings or null.

Rules mirror the receipt read model and the hub automation card: a missing
file is ``ABSENT`` (empty); a symlink, a file over ``MAX_STATE_BYTES``, bad
JSON, an unexpected shape, a duplicate task id, or an unknown status/reason is
``UNREADABLE`` and yields no missions. Callers never get an exception or a
filesystem path. Nothing here writes.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATE_NAME = "ledger_bridge_state.json"
MAX_STATE_BYTES = 1024 * 1024
MAX_MISSIONS = 2000
MAX_TEXT = 200
STALE_AFTER_SECONDS = 15 * 60
CLOCK_SKEW_SECONDS = 60
STATUSES = ("POSTED", "FINAL_DONE", "BLOCKED", "ERROR")
REASONS = ("CONTROLLER_BLOCKED", "FAILED", "CANCELLED", "GOAL_PAIR", "GOAL_TOKEN")
OPTIONAL_FIELDS = (
    "accepted_result_id",
    "claim_event_id",
    "evidence_ref",
    "goal_id",
    "reason",
    "status",
    "updated_at",
)
PUBLIC_FIELDS = ("mission_id", "task_id", "status", "reason", "goal_id", "updated_at",
                 "accepted_result_id", "claim_event_id", "evidence_ref")


class Snapshot:
    """One read of the state. ``source`` is ABSENT, OK, UNREADABLE or DEMO."""

    def __init__(self, source: str, missions: list[dict], mtime: float | None = None):
        self.source = source
        self.missions = missions
        self.mtime = mtime

    @property
    def readable(self) -> bool:
        return self.source != "UNREADABLE"


def read_state_dir(state_dir) -> Snapshot:
    path = Path(state_dir) / STATE_NAME
    try:
        if path.is_symlink():
            return Snapshot("UNREADABLE", [])
        if not path.exists():
            return Snapshot("ABSENT", [])
        if not path.is_file():
            return Snapshot("UNREADABLE", [])
        size = path.stat().st_size
        if size > MAX_STATE_BYTES:
            return Snapshot("UNREADABLE", [])
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as handle:
            raw = handle.read(MAX_STATE_BYTES + 1)
        mtime = path.stat().st_mtime
    except OSError:
        return Snapshot("UNREADABLE", [])
    if len(raw) > MAX_STATE_BYTES:
        return Snapshot("UNREADABLE", [])
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return Snapshot("UNREADABLE", [])
    return parse_document(document, source="OK", mtime=mtime)


def parse_document(document, source: str = "OK", mtime: float | None = None) -> Snapshot:
    missions = _missions(document)
    if missions is None:
        return Snapshot("UNREADABLE", [], mtime)
    return Snapshot(source, missions, mtime)


def _missions(document):
    if not isinstance(document, dict) or set(document) != {"missions"}:
        return None
    raw = document["missions"]
    rows = []
    if isinstance(raw, dict):
        items = list(raw.items())
    elif isinstance(raw, list):
        items = []
        for mapping in raw:
            if not isinstance(mapping, dict):
                return None
            items.append((mapping.get("mission_id"), mapping))
    else:
        return None
    if len(items) > MAX_MISSIONS:
        return None
    seen = set()
    for mission_id, mapping in items:
        if not _text(mission_id) or not isinstance(mapping, dict):
            return None
        if "mission_id" in mapping and mapping["mission_id"] != mission_id:
            return None
        task_id = mapping.get("task_id")
        if not _text(task_id) or task_id in seen:
            return None
        seen.add(task_id)
        row = {"mission_id": mission_id, "task_id": task_id}
        for name in OPTIONAL_FIELDS:
            value = mapping.get(name)
            if value is None:
                row[name] = None
                continue
            if not _text(value):
                return None
            row[name] = value
        if row["status"] is not None and row["status"] not in STATUSES:
            return None
        if row["reason"] is not None and row["reason"] not in REASONS:
            return None
        if row["updated_at"] is not None and parse_time(row["updated_at"]) is None:
            return None
        rows.append(row)
    rows.sort(key=lambda item: (item["updated_at"] or "", item["mission_id"]), reverse=True)
    return rows


def _text(value) -> bool:
    return isinstance(value, str) and 0 < len(value) <= MAX_TEXT and value.isprintable()


def parse_time(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        moment = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return moment.astimezone(timezone.utc)


def effective_status(row: dict) -> str:
    """Older files lack ``status``: a result means FINAL_DONE, otherwise POSTED."""
    if row["status"] is not None:
        return row["status"]
    return "FINAL_DONE" if row["accepted_result_id"] else "POSTED"


def automation_card(snapshot: Snapshot, now: datetime) -> dict:
    """Same precedence as the hub card: ERROR > BLOCKED > RUNNING/STALE > IDLE."""
    if snapshot.source == "UNREADABLE":
        return _card("ATTENTION", "Needs attention", "The automation record could not be read.", reason="UNREADABLE")
    if snapshot.source == "ABSENT":
        return _card("NOT_CONFIGURED", "Not set up", "Courier has no automation record here.")
    rows = snapshot.missions
    ages = []
    for row in rows:
        moment = parse_time(row["updated_at"]) if row["updated_at"] else None
        if moment is None and snapshot.mtime is not None:
            moment = datetime.fromtimestamp(snapshot.mtime, tz=timezone.utc)
        if moment is None:
            ages.append(None)
            continue
        age = (now - moment).total_seconds()
        if age < -CLOCK_SKEW_SECONDS:
            return _card("ATTENTION", "Needs attention", "The automation record has a time this server does not trust.",
                         reason="CLOCK")
        ages.append(max(0, int(age)))
    statuses = [effective_status(row) for row in rows]
    errors = [row for row, status in zip(rows, statuses) if status == "ERROR"]
    if errors:
        return _card("ATTENTION", "Needs attention", f"{len(errors)} mission(s) ended in error.", reason="ERROR",
                     reason_codes=sorted({row["reason"] for row in errors if row["reason"]}))
    blocked = [row for row, status in zip(rows, statuses) if status == "BLOCKED"]
    if blocked:
        return _card("BLOCKED", "Blocked", f"{len(blocked)} mission(s) are blocked.",
                     reason_codes=sorted({row["reason"] for row in blocked if row["reason"]}))
    posted_ages = [age for age, status in zip(ages, statuses) if status == "POSTED"]
    if posted_ages:
        if any(age is None for age in posted_ages):
            return _card("ATTENTION", "Needs attention", "A running mission has no usable time.", reason="CLOCK")
        oldest = max(posted_ages)
        if oldest > STALE_AFTER_SECONDS:
            return _card("ATTENTION", "Needs attention",
                         "The automation record is too old to say whether work is still moving.", reason="STALE",
                         age_seconds=oldest)
        return _card("RUNNING", "Running", f"{len(posted_ages)} mission(s) in flight.", in_flight=len(posted_ages),
                     age_seconds=oldest)
    return _card("IDLE", "Idle", "No missions are in flight.", in_flight=0)


def _card(state, label, detail, reason=None, reason_codes=None, in_flight=None, age_seconds=None) -> dict:
    return {
        "state": state,
        "label": label,
        "detail": detail,
        "reason": reason,
        "reason_codes": list(reason_codes or []),
        "in_flight": in_flight,
        "age_seconds": age_seconds,
    }


def public_row(row: dict) -> dict:
    out = {name: row.get(name) for name in PUBLIC_FIELDS}
    out["status"] = effective_status(row)
    return out
