"""Customer card for whether local automation is in flight.

The only input is ``<home>/ledger_bridge_state.json``, the mission map written
by the ledger-to-V1 bridge. A mission may carry ``status`` (``POSTED``,
``FINAL_DONE``, ``BLOCKED``, ``ERROR``), ``reason`` (null or one of
``CONTROLLER_BLOCKED``, ``FAILED``, ``CANCELLED``, ``GOAL_PAIR``,
``GOAL_TOKEN``), and ``updated_at`` (ISO-8601 UTC ending in Z). Files written
before those fields existed are derived: a result is ``FINAL_DONE``, and a
mission with no result is ``POSTED``. This module does not read the
coordination ledger, the controller, or a token.

Any ``ERROR`` is attention. Otherwise any ``BLOCKED`` is blocked. Otherwise
any ``POSTED`` is running, unless that observation is older than
``STALE_AFTER_SECONDS``. Only ``FINAL_DONE`` is idle. An unknown status or
reason fails closed. Age uses each mission's ``updated_at`` when it is
present, and the state file's modification time otherwise.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

MAX_STATE_BYTES = 1024 * 1024
STALE_AFTER_SECONDS = 15 * 60
CLOCK_SKEW_SECONDS = 60
STATE_NAME = "ledger_bridge_state.json"
_STATUSES = frozenset({"POSTED", "FINAL_DONE", "BLOCKED", "ERROR"})
_REASONS = ("CONTROLLER_BLOCKED", "FAILED", "CANCELLED", "GOAL_PAIR", "GOAL_TOKEN")

_UNREADABLE = "The automation record could not be read."
_STALE = "The automation record is too old to say whether work is still moving."
_CLOCK = "The automation record has a time this computer does not trust."
_UNKNOWN = "The automation record has a value this hub does not recognise."


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
        missions = _missions(document, mtime, moment)
    except _Bad as exc:
        if exc.code == "UNKNOWN":
            return _attention("UNKNOWN", _UNKNOWN, age=None)
        if exc.code == "MALFORMED":
            return _attention("MALFORMED", _UNREADABLE, age=None)
        return _attention("UNREADABLE", _UNREADABLE, age=None)
    if any(item["future"] for item in missions):
        return _attention("CLOCK", _CLOCK, age=None)
    errors = [item for item in missions if item["status"] == "ERROR"]
    if errors:
        reasons = _reason_list(errors)
        return _attention("ERROR", _counted(len(errors), "ended in error", reasons), age=None, reason_codes=reasons)
    blocked = [item for item in missions if item["status"] == "BLOCKED"]
    if blocked:
        return _blocked_card(blocked)
    posted = [item for item in missions if item["status"] == "POSTED"]
    if posted:
        age = max(item["age"] for item in posted)
        if age > STALE_AFTER_SECONDS:
            return _attention("STALE", _STALE, age=age)
        return _card("RUNNING", "Running", _running_detail(len(posted), age), len(posted), age, None)
    age = max((item["age"] for item in missions), default=_file_age(mtime, moment))
    if age is None:
        return _attention("CLOCK", _CLOCK, age=None)
    return _card("IDLE", "Idle", "No missions are in flight.", 0, age, None)


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
        observed = path.stat().st_mtime
    except OSError as exc:
        raise _Bad("UNREADABLE") from exc
    if len(raw) > MAX_STATE_BYTES:
        raise _Bad("UNREADABLE")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise _Bad("UNREADABLE") from exc
    return document, observed


def _missions(document, mtime, now):
    if not isinstance(document, dict) or set(document) != {"missions"}:
        raise _Bad("MALFORMED")
    raw = document.get("missions")
    if not isinstance(raw, dict):
        raise _Bad("MALFORMED")
    file_age = _file_age(mtime, now)
    found = []
    for mission_id, mapping in raw.items():
        if not isinstance(mission_id, str) or not mission_id or not isinstance(mapping, dict):
            raise _Bad("MALFORMED")
        if not isinstance(mapping.get("task_id"), str) or not isinstance(mapping.get("idempotency_key"), str):
            raise _Bad("MALFORMED")
        if not isinstance(mapping.get("posted"), bool) or "accepted_result_id" not in mapping:
            raise _Bad("MALFORMED")
        result = mapping.get("accepted_result_id")
        if result is not None and (not isinstance(result, str) or not result):
            raise _Bad("MALFORMED")
        status, reason = _status_of(mapping)
        age, future = _mission_age(mapping, file_age, now)
        found.append({
            "id": mission_id,
            "status": status,
            "reason": reason,
            "age": age,
            "future": future,
        })
    return found


def _status_of(mapping):
    if "status" not in mapping:
        status, reason = _derive_status(mapping)
    else:
        status = mapping.get("status")
        if status not in _STATUSES:
            raise _Bad("UNKNOWN")
        reason = None if "reason" not in mapping else mapping.get("reason")
    if "status" not in mapping and "reason" in mapping:
        reason = mapping.get("reason")
    if reason is not None and reason not in _REASONS:
        raise _Bad("UNKNOWN")
    return status, reason


def _derive_status(mapping):
    """A result is finished. No result stays posted, including a claim not yet posted."""
    result = mapping.get("accepted_result_id")
    if isinstance(result, str) and result:
        return "FINAL_DONE", None
    return "POSTED", None


def _mission_age(mapping, file_age, now):
    if "updated_at" not in mapping:
        return file_age, file_age is None
    observed = _parse_updated_at(mapping.get("updated_at"))
    age = _delta_age(observed, now)
    return age, age is None


def _parse_updated_at(value):
    if not isinstance(value, str) or not value.endswith("Z") or "\n" in value or len(value) > 40:
        raise _Bad("MALFORMED")
    try:
        observed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise _Bad("MALFORMED") from exc
    if observed.tzinfo is None or observed.utcoffset() != timezone.utc.utcoffset(observed):
        raise _Bad("MALFORMED")
    return observed


def _file_age(mtime, now):
    return _delta_age(datetime.fromtimestamp(mtime, tz=timezone.utc), now)


def _delta_age(observed, now):
    delta = (now - observed).total_seconds()
    if delta < -CLOCK_SKEW_SECONDS:
        return None
    if delta < 0:
        return 0
    return int(round(delta))


def _blocked_card(blocked):
    reasons = _reason_list(blocked)
    shown = [item["id"] for item in sorted(blocked, key=lambda item: item["id"]) if _show_id(item["id"])][:5]
    count = len(blocked)
    return _card(
        "BLOCKED",
        "Blocked",
        _counted(count, "blocked", reasons, shown),
        None,
        None,
        None,
        blocked_count=count,
        mission_ids=shown,
        reason_codes=reasons,
    )


def _reason_list(items):
    found = {item["reason"] for item in items if item["reason"]}
    return [code for code in _REASONS if code in found]


def _show_id(mission_id):
    if len(mission_id) > 80:
        return False
    return not any(char in mission_id for char in "/\\\n\r\t")


def _counted(count, verb, reasons, mission_ids=None):
    if verb == "blocked":
        sentence = "1 mission is blocked." if count == 1 else f"{count} missions are blocked."
    else:
        sentence = "1 mission ended in error." if count == 1 else f"{count} missions ended in error."
    if reasons:
        sentence += " Reasons: " + ", ".join(reasons) + "."
    if mission_ids:
        sentence += " Missions: " + ", ".join(mission_ids) + "."
    return sentence


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


def _attention(reason: str, detail: str, *, age, reason_codes=None) -> dict:
    return _card("ATTENTION", "Needs attention", detail, None, age, reason, reason_codes=reason_codes)


def _card(state, label, detail, in_flight, age, reason, *, blocked_count=None, mission_ids=None, reason_codes=None) -> dict:
    return {
        "state": state,
        "label": label,
        "detail": detail,
        "in_flight": in_flight,
        "record_age_seconds": age,
        "reason_code": reason,
        "blocked_count": blocked_count,
        "mission_ids": mission_ids,
        "reason_codes": reason_codes,
    }
