"""The Courier v1 controller: the only writer of the journal.

Everything the controller knows durably comes from courier_core.journal; the
only extra state it keeps is in memory and is rebuilt on boot:

- leases: dispatch_id -> monotonic deadline. Deadlines never enter the
  journal or a projection. A heartbeat moves the deadline to now + ttl; a
  missed deadline appends LEASE_EXPIRED(reason=ttl). After a restart every
  open attempt gets one fresh ttl of grace; if no heartbeat arrives in that
  window the lease expires with reason=restart_grace.
- the verification queue: tasks in VERIFYING. It is refilled from the
  projection on boot.

After any failure (lease lost, result rejected) the controller journals the
decision the state machine allows: retry, fail, BLOCKED (an uncertain outcome
of anything not classified idempotent is never retried) or CANCELLED. A
BLOCKED task waits for a human decision with an actor (resolve()).

Attribution: CONTROLLER_STARTED records the build (courier_core.build);
RESULT_ACCEPTED / RESULT_REJECTED record the verifier that decided.

Integrity: on boot an existing journal is opened read-only and checked
(SQLite quick_check, hash chain, append-only guards, projection == replay)
before anything is written. Any defect puts the controller in
degraded_readonly: reads and the event stream work, every write is refused,
and the file is left exactly as found.

All mutations run under one lock with a finite acquisition timeout, so a
request either completes or fails fast with "busy"; nothing waits forever.
"""

from __future__ import annotations

import hashlib
import logging
import os
import queue
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from courier_core.build import build_identity
from courier_core.events import (
    EFFECT_CLASSES, MAX_ATTEMPTS_LIMIT, MAX_ID_LENGTH, RESULT_OUTCOMES, Event, EventType, EventValidationError,
    effect_key,
)
from courier_core.journal import DedupeConflict, Journal, JournalError
from courier_core.projection import ProjectionError
from courier_core.state_machine import (
    ACTIVE_LEASE, TERMINAL, Decision, TaskState, TaskStatus, TransitionError, decide_after_failure,
)
from courier_core.verification import ADAPTER_NAME, VerifyFn, adapter_verifier, run_verifier

log = logging.getLogger("courier.controller")

NORMAL = "normal"
DEGRADED = "degraded_readonly"

MAX_LEASE_TTL_S = 3600
MAX_TIMEOUT_S = 7 * 24 * 3600
MAX_HEARTBEAT_DISPATCHES = 256
MAX_ARTIFACTS = 1000
SUSPEND_GAP_S = 5.0  # a tick gap this long means the machine slept; leases are not punished for it

TASK_FIELDS = {"adapter", "params", "effect_class", "max_attempts", "lease_ttl_s", "timeout_s", "idempotency_key"}
RESULT_FIELDS = {"dispatch_id", "result_id", "artifacts", "outcome", "retryable", "reason"}
MAX_REASON_CHARS = 2000

# POST /v1/tasks/<id>/resolve: the human decisions a BLOCKED task accepts.
RESOLVE_DECISIONS = {"effect_confirmed": EventType.EFFECT_CONFIRMED,
                     "retry_authorized": EventType.RETRY_AUTHORIZED,
                     "cancel": EventType.TASK_CANCELLED}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str = "", **extra: Any):
        super().__init__(message or code)
        self.status, self.code, self.message, self.extra = status, code, message or code, extra

    def body(self) -> dict:
        return {"error": self.code, "message": self.message, **self.extra}


@dataclass
class Lease:
    task_id: str
    dispatch_id: str
    worker_id: str
    ttl_s: int
    deadline: float
    reason: str  # what an expiry would be journaled as: "ttl" or "restart_grace"


def heartbeat_interval(ttl_s: int) -> float:
    """Recommended worker heartbeat: at least three beats per lease window."""
    return max(0.5, ttl_s / 3.0)



import re

class WorkerIdentity(str):
    PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

    @classmethod
    def parse(cls, value: str) -> "WorkerIdentity":
        if not isinstance(value, str) or not value or len(value) > MAX_ID_LENGTH:
            raise ApiError(400, "invalid_worker_id", f"worker_id must be a non-empty string of at most {MAX_ID_LENGTH} chars")
        if not cls.PATTERN.match(value) or value.upper() == "UNKNOWN" or value.upper() == "UNKNOWN_WORKER":
            raise ApiError(400, "invalid_worker_id", "malformed or unknown worker identity")
        return cls(value)

def _require_id(body: dict, name: str) -> str:

    value = body.get(name)
    if not isinstance(value, str) or not value or len(value) > MAX_ID_LENGTH:
        raise ApiError(400, "invalid_request", f"{name} must be a non-empty string of at most {MAX_ID_LENGTH} chars")
    return value


def _require_int(body: dict, name: str, low: int, high: int, required: bool = True) -> int | None:
    value = body.get(name)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ApiError(400, "invalid_request", f"{name} must be an integer between {low} and {high}")
    return value


def _require_reason(body: dict, required: bool) -> str | None:
    value = body.get("reason")
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_REASON_CHARS:
        raise ApiError(400, "invalid_request", f"reason must be a non-empty string of at most {MAX_REASON_CHARS} chars")
    return value


def _only_fields(body: Any, allowed: set[str]) -> dict:
    if not isinstance(body, dict):
        raise ApiError(400, "invalid_request", "request body must be a JSON object")
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise ApiError(400, "invalid_request", f"unknown field(s): {', '.join(unknown)}")
    return body


class Controller:
    def __init__(self, home: str | os.PathLike, *, verifier: Callable[[str], VerifyFn | None] = adapter_verifier,
                 clock: Callable[[], float] = time.monotonic, lock_timeout_s: float = 10.0):
        self.home = Path(home)
        self.db_path = self.home / "courier.db"
        self.mode = "booting"
        self.first_bad_seq: int | None = None
        self.degraded_reason: str | None = None
        self.journal: Journal | None = None
        self._verifier = verifier
        self._clock = clock
        self._lock_timeout_s = lock_timeout_s
        self._lock = threading.RLock()
        self._leases: dict[str, Lease] = {}
        self._verify_queue: queue.Queue[str] = queue.Queue()
        self._changed = threading.Condition()
        self._head_seq = 0
        self._stopping = threading.Event()
        self._threads: list[threading.Thread] = []
        self._last_tick: float | None = None
        self._projection_readable = True
        self.build = build_identity()

    # ------------------------------------------------------------------ boot
    def boot(self) -> "Controller":
        self.home.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            problem = self._inspect_existing()
            if problem is not None:
                reason, first_bad = problem
                self._enter_degraded(reason, first_bad)
                return self
        try:
            self.journal = Journal(self.db_path).open()
        except (sqlite3.DatabaseError, JournalError) as exc:
            self._enter_degraded(f"journal cannot be opened: {exc}", None)
            return self
        self.mode = NORMAL
        with self._locked():
            self._head_seq = self.journal.head()[0]
            self._append(Event(type=EventType.CONTROLLER_STARTED, payload={"pid": os.getpid(), "build": self.build}))
            self._recover()
        return self

    def _inspect_existing(self) -> tuple[str, int | None] | None:
        try:
            inspector = Journal(self.db_path, readonly=True).open()
        except (sqlite3.DatabaseError, JournalError) as exc:
            return f"journal cannot be opened: {exc}", None
        try:
            quick = inspector.quick_check()
            if quick != "ok":
                return f"sqlite quick_check failed: {quick[:300]}", None
            report = inspector.verify_chain()
            if not report.ok:
                return f"hash chain broken: {report.reason}", report.first_bad_seq
            if not inspector.guards_present():
                return "append-only guard triggers are missing", None
            # A projection from an older build is rebuilt by the writable open; a current
            # one must equal the replay exactly.
            if inspector.projection_current() and not inspector.verify_projection():
                return "stored projection differs from journal replay", None
            return None
        except (sqlite3.DatabaseError, ProjectionError, ValueError) as exc:
            return f"journal inspection failed: {type(exc).__name__}: {exc}", None
        finally:
            inspector.close()

    def _enter_degraded(self, reason: str, first_bad_seq: int | None) -> None:
        self.mode = DEGRADED
        self.degraded_reason = reason
        self.first_bad_seq = first_bad_seq
        log.error("controller is degraded_readonly: %s", reason)
        try:
            self.journal = Journal(self.db_path, readonly=True).open()
            self._head_seq = self.journal.head()[0]
            self._projection_readable = self.journal.projection_current()
        except (sqlite3.DatabaseError, JournalError):
            self.journal = None

    def _recover(self) -> None:
        """Rebuild in-memory runtime from the projection and finish pending decisions."""
        now = self._clock()
        for task in self.journal.tasks():
            if task.status in ACTIVE_LEASE:
                self._leases[task.dispatch_id] = Lease(task.task_id, task.dispatch_id, task.worker_id,
                                                       task.lease_ttl_s, now + task.lease_ttl_s, "restart_grace")
            elif task.status is TaskStatus.VERIFYING:
                self._verify_queue.put(task.task_id)
            elif task.status is TaskStatus.ACCEPTED:
                self._complete(task)
            elif task.status is TaskStatus.RETRY_PENDING:
                self._decide(task)
            elif task.cancel_requested and task.status is TaskStatus.QUEUED:
                self._append(self._task_event(EventType.TASK_CANCELLED, task))

    # ----------------------------------------------------------- primitives
    def _locked(self):
        controller = self

        class _Guard:
            def __enter__(self):
                if not controller._lock.acquire(timeout=controller._lock_timeout_s):
                    raise ApiError(503, "busy", "controller is busy; retry")
                return self

            def __exit__(self, *exc):
                controller._lock.release()

        return _Guard()

    def _require_writable(self) -> None:
        if self._stopping.is_set():
            raise ApiError(503, "stopping", "controller is shutting down")
        if self.mode != NORMAL:
            raise ApiError(503, DEGRADED, "controller is read-only", first_bad_seq=self.first_bad_seq)

    def _append(self, event: Event):
        result = self.journal.append(event)
        if not result.duplicate:
            with self._changed:
                self._head_seq = result.event.seq
                self._changed.notify_all()
        return result

    @staticmethod
    def _task_event(event_type: EventType, task: TaskState, **kw) -> Event:
        return Event(type=event_type, task_id=task.task_id, **kw)

    def _complete(self, task: TaskState) -> None:
        self._append(Event(type=EventType.TASK_COMPLETE, task_id=task.task_id, attempt=task.attempt,
                           dispatch_id=task.dispatch_id, result_id=task.accepted_result_id))

    def _decide(self, task: TaskState) -> None:
        """Journal the only legal next step for a task in RETRY_PENDING."""
        decision = decide_after_failure(task)
        reason = task.last_reason or "attempt failed"
        if decision is Decision.RETRY:
            self._append(self._task_event(EventType.TASK_RETRY_SCHEDULED, task, attempt=task.attempt,
                                          payload={"reason": reason}))
        elif decision is Decision.FAIL:
            self._append(self._task_event(EventType.TASK_FAILED, task, payload={"reason": reason}))
        elif decision is Decision.BLOCK:
            self._append(self._task_event(EventType.TASK_BLOCKED, task, payload={
                "reason": f"outcome of {task.effect_class} attempt {task.attempt} is unknown ({reason}); "
                          "needs a human decision"}))
        else:
            self._append(self._task_event(EventType.TASK_CANCELLED, task, payload={"reason": "cancelled"}))

    # ------------------------------------------------------------------ API
    def health(self) -> dict:
        body = {"mode": self.mode, "head_seq": self._head_seq, "active_leases": len(self._leases),
                "build": self.build}
        if self.mode == DEGRADED:
            body["first_bad_seq"] = self.first_bad_seq
            body["reason"] = self.degraded_reason
        return body

    def task_view(self, task_id: str) -> dict:
        if self._stopping.is_set():
            raise ApiError(503, "stopping", "controller is shutting down")
        if not self._projection_readable:
            raise ApiError(503, DEGRADED, "task state is unavailable: the projection predates this build",
                           first_bad_seq=self.first_bad_seq)
        with self._locked():
            task = self.journal.task(task_id) if self.journal else None
        if task is None:
            raise ApiError(404, "unknown_task")
        return {**task.to_record(), "effect_key": effect_key(task.task_id)}

    def create_task(self, body: Any) -> tuple[int, dict]:
        self._require_writable()
        body = _only_fields(body, TASK_FIELDS)
        adapter = _require_id(body, "adapter")
        if not ADAPTER_NAME.match(adapter):
            raise ApiError(400, "invalid_request", "adapter must match [a-z][a-z0-9_]{0,63}")
        if not isinstance(body.get("params"), dict):
            raise ApiError(400, "invalid_request", "params must be a JSON object")
        if body.get("effect_class") not in EFFECT_CLASSES:
            raise ApiError(400, "invalid_request", f"effect_class must be one of {sorted(EFFECT_CLASSES)}")
        _require_int(body, "max_attempts", 1, MAX_ATTEMPTS_LIMIT)
        _require_int(body, "lease_ttl_s", 1, MAX_LEASE_TTL_S)
        timeout_s = _require_int(body, "timeout_s", 1, MAX_TIMEOUT_S, required=False)
        key = body.get("idempotency_key")
        if key is not None:
            key = _require_id(body, "idempotency_key")
            task_id = "task-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        else:
            task_id = "task-" + uuid.uuid4().hex
        payload = {name: body[name] for name in ("adapter", "params", "effect_class", "max_attempts", "lease_ttl_s")}
        if timeout_s is not None:
            payload["timeout_s"] = timeout_s
        try:
            event = Event(type=EventType.TASK_CREATED, task_id=task_id, payload=payload)
        except EventValidationError as exc:
            raise ApiError(400, "invalid_request", str(exc)) from None
        with self._locked():
            try:
                result = self._append(event)
            except DedupeConflict:
                raise ApiError(409, "idempotency_conflict",
                               "idempotency_key was already used for a different task") from None
        return (200 if result.duplicate else 201), {"task_id": task_id, "duplicate": result.duplicate}

    def claim(self, body: Any) -> dict | None:
        self._require_writable()
        body = _only_fields(body, {"worker_id"})
        worker_id = WorkerIdentity.parse(body.get("worker_id"))
        with self._locked():
            for task in self.journal.tasks(TaskStatus.QUEUED.value):
                if task.cancel_requested:
                    continue
                dispatch_id = "dsp-" + uuid.uuid4().hex
                attempt = task.attempt + 1
                self._append(Event(type=EventType.TASK_CLAIMED, task_id=task.task_id, attempt=attempt,
                                   dispatch_id=dispatch_id, worker_id=worker_id,
                                   payload={"ttl_s": task.lease_ttl_s}))
                self._leases[dispatch_id] = Lease(task.task_id, dispatch_id, worker_id, task.lease_ttl_s,
                                                  self._clock() + task.lease_ttl_s, "ttl")
                spec = {"adapter": task.adapter, "params": task.params, "effect_class": task.effect_class,
                        "timeout_s": task.timeout_s, "effect_key": effect_key(task.task_id)}
                return {"task_id": task.task_id, "attempt": attempt, "dispatch_id": dispatch_id,
                        "worker_id": worker_id, "ttl_s": task.lease_ttl_s,
                        "heartbeat_s": heartbeat_interval(task.lease_ttl_s), "spec": spec}
        return None

    def _claim_of(self, dispatch_id: str) -> Event:
        claim = self.journal.claim_for_dispatch(dispatch_id)
        if claim is None:
            raise ApiError(404, "unknown_dispatch", "dispatch_id was never issued")
        return claim

    def start(self, body: Any) -> dict:
        self._require_writable()
        body = _only_fields(body, {"dispatch_id", "worker_id"})
        dispatch_id = _require_id(body, "dispatch_id")
        worker_id = body.get("worker_id")
        with self._locked():
            claim = self._claim_of(dispatch_id)
            if worker_id is not None and worker_id != claim.worker_id:
                raise ApiError(409, "wrong_worker", "dispatch is held by another worker")
            task = self.journal.task(claim.task_id)
            if task.dispatch_id != dispatch_id or task.status not in ACTIVE_LEASE:
                raise ApiError(409, "stale_dispatch", "dispatch is no longer active", task_status=task.status.value)
            if task.cancel_requested:
                raise ApiError(409, "cancel_requested", "task cancellation was requested; do not start")
            if task.status is TaskStatus.RUNNING:
                return {"status": "ALREADY_STARTED", "task_id": task.task_id}
            self._append(Event(type=EventType.TASK_STARTED, task_id=task.task_id, attempt=claim.attempt,
                               dispatch_id=dispatch_id, worker_id=claim.worker_id))
            return {"status": "STARTED", "task_id": task.task_id}

    def heartbeat(self, body: Any) -> dict:
        self._require_writable()
        body = _only_fields(body, {"worker_id", "dispatch_ids"})
        worker_id = WorkerIdentity.parse(body.get("worker_id"))
        dispatch_ids = body.get("dispatch_ids")
        if (not isinstance(dispatch_ids, list) or len(dispatch_ids) > MAX_HEARTBEAT_DISPATCHES
                or not all(isinstance(d, str) and 0 < len(d) <= MAX_ID_LENGTH for d in dispatch_ids)):
            raise ApiError(400, "invalid_request",
                           f"dispatch_ids must be a list of at most {MAX_HEARTBEAT_DISPATCHES} ids")
        reported = set(dispatch_ids)
        stop, cancel = [], []
        with self._locked():
            now = self._clock()
            for dispatch_id in sorted(reported):
                lease = self._leases.get(dispatch_id)
                if lease is None or lease.worker_id != worker_id:
                    stop.append(dispatch_id)
                    continue
                task = self.journal.task(lease.task_id)
                # A reporting worker is alive: keep the lease, also while it is still
                # killing a cancelled dispatch. CANCELLED needs its confirmation.
                lease.deadline = now + lease.ttl_s
                lease.reason = "ttl"
                if task.cancel_requested:
                    cancel.append(dispatch_id)
            # The worker stops reporting a cancelled dispatch only after it has reaped
            # the process tree: that absence is the cancellation confirmation.
            for lease in [l for l in self._leases.values() if l.worker_id == worker_id]:
                if lease.dispatch_id in reported:
                    continue
                task = self.journal.task(lease.task_id)
                if task.cancel_requested and task.status in ACTIVE_LEASE and task.dispatch_id == lease.dispatch_id:
                    self._append(self._task_event(EventType.TASK_CANCELLED, task,
                                                  payload={"reason": "worker confirmed stop"}))
                    del self._leases[lease.dispatch_id]
        return {"ok": True, "stop": stop, "cancel": cancel}

    def result(self, body: Any) -> tuple[int, dict]:
        self._require_writable()
        body = _only_fields(body, RESULT_FIELDS)
        dispatch_id = _require_id(body, "dispatch_id")
        result_id = _require_id(body, "result_id")
        artifacts = body.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) > MAX_ARTIFACTS:
            raise ApiError(400, "invalid_request", f"artifacts must be a list of at most {MAX_ARTIFACTS} entries")
        if body.get("outcome") not in RESULT_OUTCOMES:
            raise ApiError(400, "invalid_request", f"outcome must be one of {sorted(RESULT_OUTCOMES)}")
        payload: dict[str, Any] = {"artifacts": artifacts, "status": body["outcome"].upper()}
        if "retryable" in body:
            payload["retryable"] = body["retryable"]
        if "reason" in body:
            if not isinstance(body["reason"], str) or len(body["reason"]) > MAX_REASON_CHARS:
                raise ApiError(400, "invalid_request", f"reason must be a string of at most {MAX_REASON_CHARS} chars")
            payload["reason"] = body["reason"]
        with self._locked():
            claim = self._claim_of(dispatch_id)
            try:
                candidate = Event(type=EventType.RESULT_READY, task_id=claim.task_id, attempt=claim.attempt,
                                  dispatch_id=dispatch_id, worker_id=claim.worker_id, result_id=result_id,
                                  payload=payload)
            except EventValidationError as exc:
                raise ApiError(400, "invalid_request", str(exc)) from None
            existing = self.journal.get_event_by_dedupe_key(candidate.dedupe_key)
            if existing is not None:
                if existing.content() == candidate.content():
                    return 200, {"status": "ACK_DUPLICATE", "task_id": claim.task_id, "seq": existing.seq}
                raise ApiError(409, "result_conflict", "result_id was already used with different content")
            task = self.journal.task(claim.task_id)
            if task.dispatch_id == dispatch_id and task.status is TaskStatus.RUNNING:
                if task.cancel_requested:
                    raise ApiError(409, "cancel_requested", "task cancellation was requested; result not accepted")
                appended = self._append(candidate)
                self._leases.pop(dispatch_id, None)
                self._verify_queue.put(task.task_id)
                return 200, {"status": "ACCEPTED_FOR_VERIFY", "task_id": task.task_id, "seq": appended.event.seq}
            if task.dispatch_id == dispatch_id and task.status is TaskStatus.CLAIMED:
                raise ApiError(409, "not_started", "report /v1/start before a result")
            # The late report is kept as evidence (a human deciding a BLOCKED task needs it),
            # but it never changes the task.
            late = Event(type=EventType.LATE_RESULT_DISCARDED, task_id=task.task_id, dispatch_id=dispatch_id,
                         result_id=result_id, dedupe_key=f"late:{dispatch_id}:{result_id}",
                         payload={**payload, "reported_reason": payload.get("reason"), "attempt": claim.attempt,
                                  "reason": f"dispatch is not the active attempt (task {task.status.value})"})
            try:
                self._append(late)
            except (TransitionError, DedupeConflict):  # pragma: no cover - defensive
                pass
            raise ApiError(409, "stale_dispatch", "result belongs to a superseded or finished dispatch",
                           task_status=task.status.value)

    def cancel(self, task_id: str, body: Any = None) -> dict:
        """Request cancellation. Cancelling a BLOCKED task is a human decision: it needs an actor."""
        self._require_writable()
        body = _only_fields(body or {}, {"actor", "reason"})
        actor = _require_id(body, "actor") if body.get("actor") is not None else None
        reason = _require_reason(body, required=False)
        with self._locked():
            task = self.journal.task(task_id)
            if task is None:
                raise ApiError(404, "unknown_task")
            return self._cancel(task, actor, reason)

    def _cancel(self, task: TaskState, actor: str | None, reason: str | None) -> dict:
        if task.status in TERMINAL:
            raise ApiError(409, "terminal", "task already finished", task_status=task.status.value)
        if task.status is TaskStatus.BLOCKED and actor is None:
            raise ApiError(409, "actor_required", "cancelling a blocked task is a human decision; name the actor",
                           task_status=task.status.value)
        who = {"actor": actor} if actor is not None else {}
        if not task.cancel_requested:
            self._append(self._task_event(EventType.TASK_CANCEL_REQUESTED, task,
                                          payload={"reason": reason or "requested via API", **who}))
            task = self.journal.task(task.task_id)
        if task.status in (TaskStatus.QUEUED, TaskStatus.BLOCKED):
            self._append(self._task_event(EventType.TASK_CANCELLED, task,
                                          payload={"reason": reason or "cancelled", **who}))
        elif task.status is TaskStatus.RETRY_PENDING:
            self._decide(task)
        return {"status": self.journal.task(task.task_id).status.value, "cancel_requested": True}

    def resolve(self, task_id: str, body: Any) -> dict:
        """A human decision on a BLOCKED task: effect_confirmed, retry_authorized or cancel.

        The body names the blocked attempt it decides about, so a stale or
        repeated click cannot act on a later block of the same task.
        """
        self._require_writable()
        body = _only_fields(body, {"decision", "actor", "attempt", "reason"})
        decision = body.get("decision")
        if decision not in RESOLVE_DECISIONS:
            raise ApiError(400, "invalid_request", f"decision must be one of {sorted(RESOLVE_DECISIONS)}")
        actor = _require_id(body, "actor")
        attempt = _require_int(body, "attempt", 1, MAX_ATTEMPTS_LIMIT)
        reason = _require_reason(body, required=True)
        event_type = RESOLVE_DECISIONS[decision]
        with self._locked():
            task = self.journal.task(task_id)
            if task is None:
                raise ApiError(404, "unknown_task")
            if event_type is not EventType.TASK_CANCELLED:
                candidate = Event(type=event_type, task_id=task_id, attempt=attempt,
                                  payload={"actor": actor, "reason": reason})
                existing = self.journal.get_event_by_dedupe_key(candidate.dedupe_key)
                if existing is not None:
                    if existing.content() != candidate.content():
                        raise ApiError(409, "decision_conflict", "this attempt was already decided differently")
                    return {"status": task.status.value, "decision": decision, "duplicate": True}
            if task.status is not TaskStatus.BLOCKED:
                raise ApiError(409, "not_blocked", "only a blocked task takes a human decision",
                               task_status=task.status.value)
            if attempt != task.attempt:
                raise ApiError(409, "stale_decision", f"the blocked attempt is {task.attempt}",
                               task_status=task.status.value, attempt=task.attempt)
            if event_type is EventType.TASK_CANCELLED:
                result = self._cancel(task, actor, reason)
                return {"status": result["status"], "decision": decision, "duplicate": False}
            if event_type is EventType.RETRY_AUTHORIZED and task.cancel_requested:
                raise ApiError(409, "cancel_requested", "cancellation was requested; cancel or confirm the effect")
            if event_type is EventType.RETRY_AUTHORIZED and task.attempt >= MAX_ATTEMPTS_LIMIT:
                raise ApiError(409, "attempt_limit", f"attempt limit {MAX_ATTEMPTS_LIMIT} reached")
            self._append(candidate)
            return {"status": self.journal.task(task_id).status.value, "decision": decision, "duplicate": False}

    # ------------------------------------------------------- background work
    def tick(self) -> None:
        """Expire missed leases (one pass); called by the ticker thread and tests."""
        if self.mode != NORMAL or self._stopping.is_set():
            return
        with self._locked():
            if self._stopping.is_set():
                return
            now = self._clock()
            if self._last_tick is not None and now - self._last_tick > SUSPEND_GAP_S:
                gap = now - self._last_tick
                for lease in self._leases.values():
                    lease.deadline += gap
                log.warning("tick gap of %.1fs (suspend?); lease deadlines extended", gap)
            self._last_tick = now
            for lease in [l for l in self._leases.values() if l.deadline <= now]:
                del self._leases[lease.dispatch_id]
                task = self.journal.task(lease.task_id)
                if task is None or task.dispatch_id != lease.dispatch_id or task.status not in ACTIVE_LEASE:
                    continue
                self._append(Event(type=EventType.LEASE_EXPIRED, task_id=task.task_id, attempt=task.attempt,
                                   dispatch_id=task.dispatch_id, worker_id=task.worker_id,
                                   payload={"reason": lease.reason}))
                self._decide(self.journal.task(task.task_id))

    def verify_next(self, timeout: float = 0.0) -> bool:
        """Verify one queued result; returns False if the queue was empty."""
        try:
            task_id = self._verify_queue.get(timeout=timeout) if timeout else self._verify_queue.get_nowait()
        except queue.Empty:
            return False
        with self._locked():
            task = self.journal.task(task_id)
            if task is None or task.status is not TaskStatus.VERIFYING:
                return True
            result = self.journal.get_event_by_dedupe_key(f"result:{task.dispatch_id}:{task.pending_result_id}")
        verdict = run_verifier(self._verifier, task, result, self.home)  # outside the lock: may be slow
        with self._locked():
            if self._stopping.is_set():
                return True  # the task stays VERIFYING; the next boot re-verifies it
            current = self.journal.task(task_id)
            if (current.status is not TaskStatus.VERIFYING or current.pending_result_id != task.pending_result_id
                    or current.dispatch_id != task.dispatch_id):
                return True
            common = dict(task_id=task_id, attempt=current.attempt, dispatch_id=current.dispatch_id,
                          result_id=current.pending_result_id)
            if verdict.accepted:
                self._append(Event(type=EventType.RESULT_ACCEPTED, **common,
                                   payload={"reason": verdict.reason, "verifier": verdict.verifier}))
                self._complete(self.journal.task(task_id))
            else:
                self._append(Event(type=EventType.RESULT_REJECTED, **common,
                                   payload={"reason": verdict.reason or "rejected", "retryable": verdict.retryable,
                                            "verifier": verdict.verifier}))
                self._decide(self.journal.task(task_id))
        return True

    def drain(self) -> None:
        """Run all pending verifications synchronously (tests and shutdown)."""
        while self.verify_next():
            pass

    def start_background(self, tick_s: float = 0.25) -> None:
        if self.mode != NORMAL:
            return

        def ticker():
            while not self._stopping.wait(tick_s if self._leases else 1.0):
                try:
                    self.tick()
                except ApiError:
                    continue
                except Exception:  # noqa: BLE001 - keep the controller alive, but loudly
                    log.exception("lease ticker failed")

        def verifier():
            while not self._stopping.is_set():
                try:
                    self.verify_next(timeout=0.5)
                except ApiError:
                    continue
                except Exception:  # noqa: BLE001
                    log.exception("verification failed")

        for target, name in ((ticker, "courier-lease-ticker"), (verifier, "courier-verifier")):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self._threads.append(thread)

    # -------------------------------------------------------- event stream
    def events_after(self, after_seq: int, limit: int = 500) -> list[Event]:
        """Committed events with seq > after_seq, read on a private connection."""
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(self.db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM events WHERE seq > ? ORDER BY seq LIMIT ?",
                                (after_seq, limit)).fetchall()
        except sqlite3.DatabaseError:
            return []
        finally:
            conn.close()
        events = []
        for row in rows:
            try:
                events.append(Event.from_row(row))
            except (EventValidationError, ValueError):
                break  # never stream past a row that does not validate
        return events

    def wait_for_change(self, after_seq: int, timeout: float) -> None:
        with self._changed:
            if self._head_seq <= after_seq and not self._stopping.is_set():
                self._changed.wait(timeout)

    @property
    def stopping(self) -> bool:
        return self._stopping.is_set()

    # --------------------------------------------------------------- stop
    def stop(self, join_timeout_s: float = 5.0) -> None:
        self._stopping.set()
        with self._changed:
            self._changed.notify_all()
        for thread in self._threads:
            thread.join(timeout=join_timeout_s)
        if self.journal is None:
            return
        try:
            with self._locked():
                if self.mode == NORMAL:
                    self._append(Event(type=EventType.CONTROLLER_STOPPED, payload={"pid": os.getpid()}))
                self.journal.close()
        except ApiError:
            log.error("could not acquire the controller lock to close the journal cleanly")
        self.journal = None

