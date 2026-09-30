"""Desktop overlay: event-log persistence and crash recovery.

The overlay visualizes agent lifecycle events but never steers execution.
This module persists those events (JSON lines, fsync) plus atomic snapshots
so a restarted overlay can rebuild its view: load snapshot, replay the log
tail through a caller-supplied ``apply`` function. No agent control, no
network, no secrets: event dicts carrying secret-looking keys are rejected
fail-closed at append time.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

EVENT_TYPES = (
    "ORCHESTRATOR_CREATED_TASK",
    "TASK_ASSIGNED",
    "COURIER_PICKUP",
    "CUSTOMS_ENTER",
    "CUSTOMS_APPROVED",
    "CUSTOMS_REJECTED",
    "WORKER_CLAIMED",
    "WORKER_STARTED",
    "WORKER_PROGRESS",
    "RESULT_READY",
    "RESULT_CUSTOMS_CHECK",
    "RESULT_APPROVED",
    "RESULT_REJECTED",
    "COURIER_RETURN",
    "TASK_COMPLETE",
    "TASK_BLOCKED",
)

# Top-level keys that must never be persisted into the event log.
_SECRET_KEYS = ("api_key", "api-key", "secret", "password", "bearer_token")


def _check_event(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("event must be a JSON object")
    kind = event.get("type")
    if not isinstance(kind, str) or not kind or len(kind) > 64:
        raise ValueError("event field 'type' must be a non-empty string (<=64)")
    for key in event:
        if not isinstance(key, str):
            raise ValueError("event keys must be strings")
        if key.lower() in _SECRET_KEYS:
            raise ValueError(f"event must not carry secret key {key!r}")
    return event


class EventLog:
    """Append-only JSON-lines event log with torn-tail detection."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def append(self, event: dict[str, Any]) -> None:
        """Persist one event (fsync). Raises on malformed or secret-bearing input."""
        _check_event(event)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def read(self) -> tuple[list[dict[str, Any]], int]:
        """Return (events, torn). A corrupt FINAL line (crash mid-write) is
        counted as torn and skipped; corruption anywhere else raises."""
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return [], 0
        events: list[dict[str, Any]] = []
        torn = 0
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                if index == len(lines) - 1:
                    torn += 1
                    continue
                raise ValueError(f"corrupt event at log line {index + 1}") from None
            if not isinstance(parsed, dict):
                raise ValueError(f"corrupt event at log line {index + 1}")
            events.append(parsed)
        return events, torn


def save_snapshot(path: str | Path, state: dict[str, Any], event_count: int) -> None:
    """Atomically persist (state, event_count). event_count is the number of
    log events already reflected in state, so recovery replays only the tail."""
    if not isinstance(state, dict):
        raise ValueError("snapshot state must be a JSON object")
    if not isinstance(event_count, int) or isinstance(event_count, bool) or event_count < 0:
        raise ValueError("event_count must be a non-negative int")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    payload = json.dumps({"state": state, "event_count": event_count}, sort_keys=True)
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)


def load_snapshot(path: str | Path) -> tuple[dict[str, Any], int]:
    """Return (state, event_count). Missing file raises FileNotFoundError
    (caller decides fresh start); corrupt content raises ValueError."""
    raw = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("corrupt snapshot") from None
    if not isinstance(data, dict) or not isinstance(data.get("state"), dict):
        raise ValueError("corrupt snapshot")
    count = data.get("event_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("corrupt snapshot")
    return data["state"], count


def recover(
    log_path: str | Path,
    snapshot_path: str | Path,
    apply: Callable[[dict[str, Any], dict[str, Any]], None],
) -> dict[str, Any]:
    """Rebuild overlay state: load snapshot (fresh {} when absent), replay
    log events after snapshot.event_count through apply(state, event).
    Returns a summary dict. Raises when the log is shorter than the snapshot
    offset (truncation/rotation must never silently drop history)."""
    try:
        state, offset = load_snapshot(snapshot_path)
    except FileNotFoundError:
        state, offset = {}, 0
    events, torn = EventLog(log_path).read()
    if offset > len(events):
        raise ValueError("snapshot offset beyond log end: log truncated?")
    replayed = 0
    for event in events[offset:]:
        apply(state, event)
        replayed += 1
    return {
        "state": state,
        "replayed": replayed,
        "torn": torn,
        "log_events": len(events),
        "snapshot_events": offset,
    }
