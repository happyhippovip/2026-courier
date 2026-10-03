"""Courier v1 event model: the only vocabulary the journal accepts.

Every state change in Courier is one immutable event appended to the SQLite
journal (courier_core.journal). This module defines the event types, the
fields each type must carry, payload validation, default de-duplication keys
and the canonical encoding that the hash chain is computed over.

Nothing here touches the database or the clock beyond producing a default
timestamp, so it can be used by the controller, the verifier, replay and
tests alike.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

SCHEMA_VERSION = 1
GENESIS_HASH = "0" * 64
MAX_ID_LENGTH = 200
MAX_ATTEMPTS_LIMIT = 100

# Intake accepts only these classes. Retry decisions treat every class other
# than "idempotent" as unsafe (courier_core.state_machine.may_auto_retry), so a
# class added here later can never become retryable by omission.
EFFECT_CLASSES = frozenset({"idempotent", "non_idempotent"})
RETRY_SAFE_EFFECT_CLASS = "idempotent"
LEASE_EXPIRY_REASONS = frozenset({"ttl", "restart_grace"})
RESULT_OUTCOMES = frozenset({"success", "failure"})

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class EventType(str, Enum):
    TASK_CREATED = "TASK_CREATED"
    TASK_CLAIMED = "TASK_CLAIMED"
    TASK_STARTED = "TASK_STARTED"
    TASK_PROGRESS = "TASK_PROGRESS"
    RESULT_READY = "RESULT_READY"
    RESULT_ACCEPTED = "RESULT_ACCEPTED"
    RESULT_REJECTED = "RESULT_REJECTED"
    TASK_COMPLETE = "TASK_COMPLETE"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    TASK_RETRY_SCHEDULED = "TASK_RETRY_SCHEDULED"
    TASK_BLOCKED = "TASK_BLOCKED"
    TASK_FAILED = "TASK_FAILED"
    TASK_CANCEL_REQUESTED = "TASK_CANCEL_REQUESTED"
    TASK_CANCELLED = "TASK_CANCELLED"
    EFFECT_CONFIRMED = "EFFECT_CONFIRMED"
    RETRY_AUTHORIZED = "RETRY_AUTHORIZED"
    LATE_RESULT_DISCARDED = "LATE_RESULT_DISCARDED"
    CONTROLLER_STARTED = "CONTROLLER_STARTED"
    CONTROLLER_STOPPED = "CONTROLLER_STOPPED"


SYSTEM_EVENTS = frozenset({EventType.CONTROLLER_STARTED, EventType.CONTROLLER_STOPPED})
TASK_EVENTS = frozenset(EventType) - SYSTEM_EVENTS

ID_FIELDS = ("task_id", "dispatch_id", "worker_id")

# Human decisions on a BLOCKED task: who decided is part of the event.
HUMAN_DECISIONS = frozenset({EventType.EFFECT_CONFIRMED, EventType.RETRY_AUTHORIZED})

# type -> (required envelope fields, required payload keys)
REQUIRED: dict[EventType, tuple[tuple[str, ...], tuple[str, ...]]] = {
    EventType.TASK_CREATED: (("task_id",), ("adapter", "params", "effect_class", "max_attempts", "lease_ttl_s")),
    EventType.TASK_CLAIMED: (("task_id", "attempt", "dispatch_id", "worker_id"), ("ttl_s",)),
    EventType.TASK_STARTED: (("task_id", "attempt", "dispatch_id", "worker_id"), ()),
    EventType.TASK_PROGRESS: (("task_id", "attempt", "dispatch_id"), ()),
    EventType.RESULT_READY: (("task_id", "attempt", "dispatch_id", "worker_id"), ("artifacts", "status")),
    EventType.RESULT_ACCEPTED: (("task_id", "attempt", "dispatch_id", "result_id"), ()),
    EventType.RESULT_REJECTED: (("task_id", "attempt", "dispatch_id", "result_id"), ("reason", "retryable")),
    EventType.TASK_COMPLETE: (("task_id", "attempt", "dispatch_id", "result_id"), ()),
    EventType.LEASE_EXPIRED: (("task_id", "attempt", "dispatch_id", "worker_id"), ("reason",)),
    EventType.TASK_RETRY_SCHEDULED: (("task_id", "attempt"), ("reason",)),
    EventType.TASK_BLOCKED: (("task_id",), ("reason",)),
    EventType.TASK_FAILED: (("task_id",), ("reason",)),
    EventType.TASK_CANCEL_REQUESTED: (("task_id",), ()),
    EventType.TASK_CANCELLED: (("task_id",), ()),
    EventType.LATE_RESULT_DISCARDED: (("task_id", "dispatch_id", "result_id"), ("reason",)),
    EventType.EFFECT_CONFIRMED: (("task_id", "attempt"), ("actor", "reason")),
    EventType.RETRY_AUTHORIZED: (("task_id", "attempt"), ("actor", "reason")),
    EventType.CONTROLLER_STARTED: ((), ()),
    EventType.CONTROLLER_STOPPED: ((), ()),
}


class EventValidationError(ValueError):
    """An event is malformed and must never reach the journal."""


def new_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex


def effect_key(task_id: str) -> str:
    """The stable logical key of the external effect a task intends.

    It depends on the task alone, so every attempt of the task (automatic
    retries and human-authorized retries alike) carries the same key. Adapters
    pass it to providers as their idempotency key, so a provider can refuse a
    second copy of an effect the controller could not see complete.
    """
    return "cfx-" + hashlib.sha256(f"courier-effect-v1:{task_id}".encode("utf-8")).hexdigest()[:40]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_json(value: Any) -> str:
    """The single JSON encoding used for payload storage and hashing."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def default_dedupe_key(event_type: EventType, task_id: str | None, attempt: int | None,
                       dispatch_id: str | None, result_id: str | None) -> str | None:
    """Keys that make the journal itself refuse a second copy of an effect.

    RESULT_READY is idempotent per (dispatch_id, result_id): a worker that
    re-sends its outbox gets an acknowledgement, not a second event. A task is
    created, accepted and completed at most once; each attempt is claimed,
    started and lease-expired at most once.
    """
    if event_type is EventType.TASK_CREATED:
        return f"created:{task_id}"
    if event_type is EventType.TASK_CLAIMED:
        return f"claim:{task_id}:{attempt}"
    if event_type is EventType.TASK_STARTED:
        return f"start:{dispatch_id}"
    if event_type is EventType.RESULT_READY:
        return f"result:{dispatch_id}:{result_id}"
    if event_type is EventType.RESULT_ACCEPTED:
        return f"accepted:{task_id}"
    if event_type is EventType.TASK_COMPLETE:
        return f"complete:{task_id}"
    if event_type is EventType.LEASE_EXPIRED:
        return f"lease_expired:{dispatch_id}"
    if event_type is EventType.EFFECT_CONFIRMED:
        return f"effect_confirmed:{task_id}"
    if event_type is EventType.RETRY_AUTHORIZED:
        return f"retry_authorized:{task_id}:{attempt}"
    return None


@dataclass(frozen=True)
class Event:
    """One journal entry. seq / prev_hash / hash are assigned by the journal."""

    type: EventType
    task_id: str | None = None
    attempt: int | None = None
    dispatch_id: str | None = None
    worker_id: str | None = None
    result_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=new_id)
    ts_utc: str = field(default_factory=utc_now)
    dedupe_key: str | None = None
    schema_v: int = SCHEMA_VERSION
    seq: int | None = None
    prev_hash: str | None = None
    hash: str | None = None

    def __post_init__(self):
        try:
            event_type = EventType(self.type)
        except ValueError:
            raise EventValidationError(f"unknown event type: {self.type!r}") from None
        object.__setattr__(self, "type", event_type)
        if not isinstance(self.payload, Mapping):
            raise EventValidationError("payload must be a JSON object")
        try:
            # Deep copy through the canonical encoding: rejects NaN, non-string
            # keys and anything that is not plain JSON.
            payload = json.loads(canonical_json(dict(self.payload)))
        except (TypeError, ValueError) as exc:
            raise EventValidationError(f"payload is not canonical JSON: {exc}") from None
        object.__setattr__(self, "payload", payload)
        if self.dedupe_key is None:
            object.__setattr__(self, "dedupe_key", default_dedupe_key(
                event_type, self.task_id, self.attempt, self.dispatch_id, self.result_id))
        validate(self)

    @property
    def payload_json(self) -> str:
        return canonical_json(self.payload)

    def content(self) -> tuple:
        """What makes two submissions 'the same effect' (ids and time excluded)."""
        return (self.type.value, self.task_id, self.attempt, self.dispatch_id, self.worker_id,
                self.result_id, self.payload_json)

    def sealed(self, seq: int, prev_hash: str) -> "Event":
        sealed = replace(self, seq=seq, prev_hash=prev_hash, hash=None)
        return replace(sealed, hash=chain_hash(sealed))

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Event":
        return cls(
            type=row["type"], task_id=row["task_id"], attempt=row["attempt"],
            dispatch_id=row["dispatch_id"], worker_id=row["worker_id"], result_id=row["result_id"],
            payload=json.loads(row["payload"]), event_id=row["event_id"], ts_utc=row["ts_utc"],
            dedupe_key=row["dedupe_key"], schema_v=row["schema_v"], seq=row["seq"],
            prev_hash=row["prev_hash"], hash=row["hash"])


def chain_hash(event: Event, payload_text: str | None = None) -> str:
    """sha256 over the canonical encoding of every stored column but the hash.

    payload_text lets the verifier hash the bytes actually stored, so any
    edit of a stored row (even one that keeps valid JSON) breaks the chain.
    """
    material = [
        event.schema_v, event.seq, event.event_id, event.type.value, event.task_id, event.attempt,
        event.dispatch_id, event.worker_id, event.result_id, event.dedupe_key, event.ts_utc,
        event.payload_json if payload_text is None else payload_text, event.prev_hash,
    ]
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def _check_id(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value or len(value) > MAX_ID_LENGTH:
        raise EventValidationError(f"{name} must be a non-empty string of at most {MAX_ID_LENGTH} chars")


def _check_positive_int(name: str, value: Any, upper: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or (upper and value > upper):
        bound = f" and <= {upper}" if upper else ""
        raise EventValidationError(f"{name} must be an integer >= 1{bound}")


def validate(event: Event) -> None:
    if event.schema_v != SCHEMA_VERSION:
        raise EventValidationError(f"unsupported schema_v {event.schema_v}")
    _check_id("event_id", event.event_id)
    if not isinstance(event.ts_utc, str) or not event.ts_utc.endswith("Z"):
        raise EventValidationError("ts_utc must be an ISO-8601 UTC string ending in 'Z'")
    if event.dedupe_key is not None:
        _check_id("dedupe_key", event.dedupe_key)

    envelope, payload_keys = REQUIRED[event.type]
    for name in envelope:
        if getattr(event, name) is None:
            raise EventValidationError(f"{event.type.value} requires {name}")
    if event.type in SYSTEM_EVENTS:
        for name in ("task_id", "attempt", "dispatch_id", "worker_id", "result_id"):
            if getattr(event, name) is not None:
                raise EventValidationError(f"{event.type.value} is a system event and takes no {name}")
    for name in ID_FIELDS:
        if getattr(event, name) is not None:
            _check_id(name, getattr(event, name))
    if event.attempt is not None:
        _check_positive_int("attempt", event.attempt, MAX_ATTEMPTS_LIMIT)
    missing = [key for key in payload_keys if key not in event.payload]
    if missing:
        raise EventValidationError(f"{event.type.value} payload requires {', '.join(missing)}")
    _validate_payload(event)


def _validate_payload(event: Event) -> None:
    payload = event.payload
    if event.type is EventType.TASK_CREATED:
        _check_id("adapter", payload["adapter"])
        if not isinstance(payload["params"], dict):
            raise EventValidationError("params must be an object")
        if payload["effect_class"] not in EFFECT_CLASSES:
            raise EventValidationError(f"effect_class must be one of {sorted(EFFECT_CLASSES)}")
        _check_positive_int("max_attempts", payload["max_attempts"], MAX_ATTEMPTS_LIMIT)
        _check_positive_int("lease_ttl_s", payload["lease_ttl_s"])
        if payload.get("timeout_s") is not None:
            _check_positive_int("timeout_s", payload["timeout_s"])
    elif event.type is EventType.TASK_CLAIMED:
        _check_positive_int("ttl_s", payload["ttl_s"])
    elif event.type is EventType.RESULT_READY:
        if payload["status"] not in ("SUCCESS", "FAILED"):
            raise EventValidationError("status must be SUCCESS or FAILED")
        artifacts = payload["artifacts"]
        if not isinstance(artifacts, list):
            raise EventValidationError("artifacts must be a list")
        for artifact in artifacts:
            if (not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str)
                    or not artifact["path"] or not _SHA256_HEX.match(str(artifact.get("sha256", "")))):
                raise EventValidationError("each artifact needs a non-empty path and a lowercase sha256")
        if "retryable" in payload and not isinstance(payload["retryable"], bool):
            raise EventValidationError("retryable must be a boolean")
    elif event.type is EventType.RESULT_REJECTED:
        if not isinstance(payload["retryable"], bool):
            raise EventValidationError("retryable must be a boolean")
    elif event.type is EventType.LEASE_EXPIRED:
        if payload["reason"] not in LEASE_EXPIRY_REASONS:
            raise EventValidationError(f"lease expiry reason must be one of {sorted(LEASE_EXPIRY_REASONS)}")
    if event.type in HUMAN_DECISIONS or "actor" in payload:
        _check_id("actor", payload.get("actor"))
    if event.type in HUMAN_DECISIONS and (not isinstance(payload["reason"], str) or not payload["reason"].strip()):
        raise EventValidationError(f"{event.type.value} needs a non-empty reason")
