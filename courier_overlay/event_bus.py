"""Local Courier event bus (overlay visualization only).

Append-only JSONL bus decoupling the desktop overlay from agent execution.
Agents/clients only ever *report* their own lifecycle state here; the bus
never controls workers, windows, or input devices.

Event envelope (exactly these fields, no secrets, no full prompts):
    {"agent_id": str, "task_id": str, "event_type": str,
     "short_summary": str, "timestamp": str (UTC ISO-8601)}
"""

import datetime
import json
import os
import re

EVENT_TYPES = frozenset({
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
})

MAX_SUMMARY_LEN = 240

# Conservative secret-shape guard: values that look like credentials are
# rejected instead of persisted. Field names are covered too (e.g. a summary
# shaped like "api_key=...").
_SECRET_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"api[_-]?key\s*[:=]",
    r"bearer\s+[A-Za-z0-9\-._~+/]+=*",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"password\s*[:=]",
    r"secret\s*[:=]",
    r"token\s*[:=]",
))


class EventBusError(ValueError):
    """Raised when an event violates the bus contract (never persisted)."""


def _utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def validate_event(agent_id, task_id, event_type, short_summary):
    """Validate envelope fields. Returns normalized dict or raises EventBusError."""
    for name, value in (("agent_id", agent_id), ("task_id", task_id)):
        if not isinstance(value, str) or not value.strip():
            raise EventBusError(f"{name} must be a non-empty string")
        if len(value) > 128:
            raise EventBusError(f"{name} exceeds 128 chars")
    if event_type not in EVENT_TYPES:
        raise EventBusError(f"unknown event_type: {event_type!r}")
    if not isinstance(short_summary, str) or not short_summary.strip():
        raise EventBusError("short_summary must be a non-empty string")
    if len(short_summary) > MAX_SUMMARY_LEN:
        raise EventBusError(f"short_summary exceeds {MAX_SUMMARY_LEN} chars")
    for pattern in _SECRET_PATTERNS:
        if pattern.search(short_summary):
            raise EventBusError("short_summary looks like it carries a secret")
    return {
        "agent_id": agent_id.strip(),
        "task_id": task_id.strip(),
        "event_type": event_type,
        "short_summary": short_summary.strip(),
        "timestamp": _utcnow(),
    }


def _fsync_dir(path):
    """fsync the containing directory so a new file entry is durable.

    Without this, file data can be fsynced yet the directory entry lost
    on OS crash, making the whole bus file vanish after restart.
    POSIX-only: directory fsync is unsupported on Windows (no-op there).
    """
    if os.name != "posix":
        return
    dir_fd = os.open(os.path.dirname(os.path.abspath(path)), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def emit(bus_path, agent_id, task_id, event_type, short_summary):
    """Validate + append one event atomically. Returns the stored record.

    Durability failures (fsync) raise OSError AFTER the record was appended;
    callers may retry — duplicates fold last-writer-wins on replay.

    Delivery is AT-LEAST-ONCE: a retry after any failure (including a
    timeout whose write actually landed) appends a second record. Consumers
    MUST fold idempotently (key on task_id + event_type, last wins) and
    MUST NOT count records. Retries MUST be bounded: unbounded retry
    against a persistent failure (e.g. full disk) grows duplicates and
    fills the disk with no backpressure from this module.
    """
    record = validate_event(agent_id, task_id, event_type, short_summary)
    os.makedirs(os.path.dirname(os.path.abspath(bus_path)), exist_ok=True)
    line = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
    with open(bus_path, "ab") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
    _fsync_dir(bus_path)
    return record


def _is_valid_record(record):
    """True iff a decoded line meets the emit contract (no re-stamping).

    The bus file is a shared local file: any process can append bytes, so
    the read path re-validates instead of trusting file content. Secret
    patterns are re-checked so a foreign-written leak never surfaces to
    overlay readers via replay.
    """
    if not isinstance(record, dict):
        return False
    for name in ("agent_id", "task_id"):
        value = record.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            return False
        if value != value.strip():
            # emit() persists stripped ids; a padded foreign id would miss
            # equality filters downstream — drop instead of repairing.
            return False
    event_type = record.get("event_type")
    if not isinstance(event_type, str) or event_type not in EVENT_TYPES:
        return False
    summary = record.get("short_summary")
    if not isinstance(summary, str) or not summary.strip():
        return False
    if len(summary) > MAX_SUMMARY_LEN:
        return False
    if summary != summary.strip():
        return False
    for pattern in _SECRET_PATTERNS:
        if pattern.search(summary):
            return False
    timestamp = record.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp:
        return False
    try:
        datetime.datetime.fromisoformat(timestamp)
    except ValueError:
        return False
    return True


def _scan_lines(bus_path):
    """Yield (record, dropped) per non-blank line; blank lines skipped.

    Single decode+validate core shared by read_events and scan_report, so
    a concurrent append cannot make the two disagree (two separate passes
    could count different file states and report negative dropped).
    """
    if not os.path.exists(bus_path):
        return
    with open(bus_path, "rb") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                yield None, True
                continue
            if not _is_valid_record(record):
                yield None, True
                continue
            yield record, False


def read_events(bus_path, event_type=None, task_id=None, agent_id=None):
    """Read back events, optionally filtered. Skips corrupt lines."""
    events = []
    for record, dropped in _scan_lines(bus_path):
        if dropped:
            continue
        if event_type is not None and record.get("event_type") != event_type:
            continue
        if task_id is not None and record.get("task_id") != task_id:
            continue
        if agent_id is not None and record.get("agent_id") != agent_id:
            continue
        events.append(record)
    return events


def replay(bus_path, **filters):
    """Yield events in stored order (generator over read_events)."""
    yield from read_events(bus_path, **filters)


def scan_report(bus_path):
    """Count total/valid/dropped lines for operator visibility.

    Drops (corrupt or schema-invalid lines, e.g. foreign-written garbage
    or secret-leak attempts) are otherwise silent. A rising dropped count
    on an unattended bus means a broken or hostile writer: investigate.
    Single pass over the shared _scan_lines core: dropped can never go
    negative, even with a concurrent writer appending mid-scan.
    """
    total = 0
    valid = 0
    for _record, dropped in _scan_lines(bus_path):
        total += 1
        if not dropped:
            valid += 1
    return {"total": total, "valid": valid, "dropped": total - valid}
