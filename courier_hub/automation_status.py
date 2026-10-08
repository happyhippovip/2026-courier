"""Customer card for whether local automation is in flight.

The only input is ``<home>/ledger_bridge_state.json``, the mission map written
by the ledger-to-V1 bridge. That file stores, per mission, ``task_id``,
``idempotency_key``, ``posted``, ``accepted_result_id``, and the bridge's
identity fields. It does not store a mission status, a blocker, or a
per-mission time. This module does not read the coordination ledger, the
controller, or a token.

An open mission is one whose ``accepted_result_id`` is null. The age shown is
the age of the state file, because the bridge rewrites that one file. A file
older than ``STALE_AFTER_SECONDS`` is not described as running.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

MAX_STATE_BYTES = 1024 * 1024
STALE_AFTER_SECONDS = 15 * 60
CLOCK_SKEW_SECONDS = 60
STATE_NAME = "ledger_bridge_state.json"

_UNREADABLE = "The automation record could not be read."
_STALE = "The automation record is too old to say whether work is still moving."
_CLOCK = "The automation record has a time this computer does not trust."


class _Bad(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def automation_card(home, now: datetime) -> dict:
    """One customer card. ``now`` may be naive; a naive value is read as UTC."""
    moment = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    path = Path(home) / STATE_NAME
    if not path.is_file():
        if path.exists():
            return _attention("UNREADABLE", _UNREADABLE, age=None)
        return _card(
            "NOT_CONFIGURED",
            "Not set up",
            "Courier has no automation record on this computer.",
            None,
            None,
            None,
        )
    try:
        document, mtime = _read_state(path)
        in_flight = _count_in_flight(document)
    except _Bad as exc:
        if exc.code == "MALFORMED":
            return _attention("MALFORMED", _UNREADABLE, age=None)
        return _attention("UNREADABLE", _UNREADABLE, age=None)
    age = _age_seconds(mtime, moment)
    if age is None:
        return _attention("CLOCK", _CLOCK, age=None)
    if in_flight and age > STALE_AFTER_SECONDS:
        return _attention("STALE", _STALE, age=age)
    if in_flight == 0:
        return _card("IDLE", "Idle", "No missions are in flight.", 0, age, None)
    return _card("RUNNING", "Running", _running_detail(in_flight, age), in_flight, age, None)


def _read_state(path: Path):
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise _Bad("UNREADABLE") from exc
    if isinstance(size, bool) or not isinstance(size, int) or size < 0 or size > MAX_STATE_BYTES:
        raise _Bad("UNREADABLE")
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_STATE_BYTES + 1)
        mtime = path.stat().st_mtime
    except OSError as exc:
        raise _Bad("UNREADABLE") from exc
    if len(raw) > MAX_STATE_BYTES:
        raise _Bad("UNREADABLE")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise _Bad("UNREADABLE") from exc
    return document, mtime


def _count_in_flight(document) -> int:
    if not isinstance(document, dict) or set(document) != {"missions"}:
        raise _Bad("MALFORMED")
    missions = document.get("missions")
    if not isinstance(missions, dict):
        raise _Bad("MALFORMED")
    open_count = 0
    for mission_id, mapping in missions.items():
        if not isinstance(mission_id, str) or not mission_id or not isinstance(mapping, dict):
            raise _Bad("MALFORMED")
        if not isinstance(mapping.get("task_id"), str) or not isinstance(mapping.get("idempotency_key"), str):
            raise _Bad("MALFORMED")
        if not isinstance(mapping.get("posted"), bool) or "accepted_result_id" not in mapping:
            raise _Bad("MALFORMED")
        result = mapping.get("accepted_result_id")
        if result is None:
            open_count += 1
            continue
        if not isinstance(result, str) or not result:
            raise _Bad("MALFORMED")
    return open_count


def _age_seconds(mtime: float, now: datetime):
    observed = datetime.fromtimestamp(mtime, tz=timezone.utc)
    delta = (now - observed).total_seconds()
    if delta < -CLOCK_SKEW_SECONDS:
        return None
    if delta < 0:
        return 0
    return int(round(delta))


def _running_detail(count: int, age: int) -> str:
    if count == 1:
        missions = "1 mission has"
    else:
        missions = f"{count} missions have"
    if age == 1:
        age_text = "1 second"
    else:
        age_text = f"{age} seconds"
    return f"{missions} no accepted result. The record is {age_text} old."


def _attention(reason: str, detail: str, *, age) -> dict:
    return _card("ATTENTION", "Needs attention", detail, None, age, reason)


def _card(state, label, detail, in_flight, age, reason) -> dict:
    return {
        "state": state,
        "label": label,
        "detail": detail,
        "in_flight": in_flight,
        "record_age_seconds": age,
        "reason_code": reason,
    }
