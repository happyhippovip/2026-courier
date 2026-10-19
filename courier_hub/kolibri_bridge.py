"""Kolibri Live Event Bridge V17: journal events -> visualizer states (read-only).

Folds Courier ledger/worker events into exactly ten visual states::

    QUEUED READY RUNNING TRANSFERRED VERIFYING VERIFIED DONE BLOCKED FAILED UNKNOWN

Fail-closed rules (no invented data, no live writes):

- A->B (ledger -> worker) advances only on a fenced TASK_CLAIMED handover;
  a TASK_STARTED without that handover stays UNKNOWN.
- B->C (worker -> verifier) advances only on a RESULT_READY handover with
  artifacts; a verdict without it stays UNKNOWN.
- DONE only on TASK_COMPLETE naming the verifier-accepted result, with the
  verifier identity retained. Human confirmations never become DONE/VERIFIED.
- Missing evidence -> UNKNOWN, and consumers must treat UNKNOWN as BLOCK
  (UNKNOWN_COST=BLOCK; see :func:`needs_human`).

The bridge never touches the journal, leases, workkeys or the network: it
folds duck-typed event objects passed in, so the controller stays the only
writer (SINGLE_WRITER=YES). Dedupe mirrors the journal (same event_id or
same dedupe_key+content -> no-op; same key with different content ->
conflict, prior state kept). Out-of-order arrivals are buffered in seq
order; replay is idempotent and never re-emits VERIFIED/DONE pulses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

STATES = (
    "QUEUED",
    "READY",
    "RUNNING",
    "TRANSFERRED",
    "VERIFYING",
    "VERIFIED",
    "DONE",
    "BLOCKED",
    "FAILED",
    "UNKNOWN",
)

_PULSE_STATES = ("VERIFIED", "DONE")
_NEEDS_HUMAN = frozenset({"UNKNOWN", "BLOCKED", "FAILED"})
_VERIFIER_KINDS = frozenset({"adapter", "courier_rule"})
_OUTCOMES = frozenset({"success", "failure"})
STALE_AFTER_S = 120.0


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_stamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _get(event: Any, name: str, default: Any = None) -> Any:
    if isinstance(event, dict):
        return event.get(name, default)
    return getattr(event, name, default)


def _etype(event: Any) -> str:
    kind = _get(event, "type")
    value = getattr(kind, "value", kind)
    return str(value) if value is not None else ""


def _payload(event: Any) -> dict:
    payload = _get(event, "payload") or {}
    return payload if isinstance(payload, dict) else {}


def _has_verifier_identity(payload: dict) -> bool:
    verifier = payload.get("verifier")
    return (
        isinstance(verifier, dict)
        and verifier.get("kind") in _VERIFIER_KINDS
        and bool(verifier.get("name"))
    )


def _has_handover_artifacts(payload: dict) -> bool:
    artifacts = payload.get("artifacts")
    return isinstance(artifacts, list) and len(artifacts) > 0


def needs_human(snapshot: dict) -> bool:
    """UNKNOWN_COST=BLOCK: these states must block A->B/B->C/DONE progress."""
    return snapshot.get("state") in _NEEDS_HUMAN or bool(snapshot.get("gap"))


def _new_record(task_id: str) -> dict:
    return {
        "task_id": task_id,
        "state": "UNKNOWN",
        "reason": "no-evidence",
        "reason_text": "No journaled event seen for this task.",
        "evidence": None,
        "attempt": 0,
        "dispatch_id": None,
        "worker_id": None,
        "pending_result_id": None,
        "accepted_result_id": None,
        "verifier": None,
        "depends_on": None,
        "last_at": None,
        "heartbeat_at": None,
        "heartbeat_alive": None,
        "late_count": 0,
        "duplicate_count": 0,
        "conflict_count": 0,
        "history_len": 0,
        "notes": [],
    }


class LiveEventBridge:
    """In-memory, read-only fold of journal events into visualizer states."""

    def __init__(self, stale_after_s: float = STALE_AFTER_S):
        self.stale_after_s = stale_after_s
        self._tasks: Dict[str, dict] = {}
        self._seen_event_ids: set = set()
        self._seen_effects: Dict[str, tuple] = {}
        self._cursor = 0
        self._pending: Dict[int, list] = {}
        self._gap_from: Optional[int] = None
        self._verified_done: set = set()
        self._pulses: List[dict] = []

    # -- intake -----------------------------------------------------------
    def ingest(self, event: Any, source: str = "live") -> dict:
        """Fold one event. Never raises on content: illegal input -> UNKNOWN."""
        seq = _get(event, "seq")
        if isinstance(seq, bool) or not isinstance(seq, int):
            return self._apply(event, source)
        if seq <= self._cursor:
            return self._replay_one(event, source)
        if seq == self._cursor + 1:
            verdict = self._apply(event, source)
            self._cursor = seq
            self._drain_pending()
            return verdict
        self._pending.setdefault(seq, []).append((event, source))
        if self._gap_from is None:
            self._gap_from = self._cursor + 1
        task_id = _get(event, "task_id")
        return {"result": "buffered", "task_id": task_id, "seq": seq,
                "waiting_for": self._cursor + 1}

    def ingest_batch(self, events: Iterable[Any], source: str = "live") -> list:
        return [self.ingest(event, source) for event in events]

    def replay(self, events: Iterable[Any]) -> list:
        """Idempotent re-fold in seq order; never emits pulses."""
        ordered = sorted(
            list(events),
            key=lambda e: (_get(e, "seq") is None, _get(e, "seq") or 0),
        )
        return [self.ingest(event, "replay") for event in ordered]

    def reconnect(self, fetch: Callable[[int], Iterable[Any]]) -> dict:
        """Pull everything after the applied cursor and fold it in order."""
        missing = list(fetch(self._cursor))
        verdicts = self.replay(missing)
        applied = sum(1 for v in verdicts if v.get("result") == "applied")
        return {"fetched": len(missing), "applied": applied,
                "cursor": self._cursor, "gap": self._gap_from}

    def note_heartbeat(self, task_id: str, at: str, alive: bool) -> None:
        rec = self._tasks.setdefault(str(task_id), _new_record(str(task_id)))
        rec["heartbeat_at"] = at
        rec["heartbeat_alive"] = bool(alive)

    # -- reads ------------------------------------------------------------
    def snapshot(self, task_id: str, now: Optional[str] = None) -> dict:
        rec = self._tasks.get(str(task_id))
        if rec is None:
            rec = _new_record(str(task_id))
        stale, stale_why = self._stale_of(rec, now or utc_now())
        evidence = dict(rec["evidence"]) if rec["evidence"] else None
        return {
            "task_id": rec["task_id"],
            "state": rec["state"],
            "reason": rec["reason"],
            "reason_text": rec["reason_text"],
            "evidence": evidence,
            "stale": stale,
            "stale_why": stale_why,
            "gap": self._gap_from,
            "late_count": rec["late_count"],
            "duplicate_count": rec["duplicate_count"],
            "conflict_count": rec["conflict_count"],
            "history_len": rec["history_len"],
            "notes": list(rec["notes"][-5:]),
        }

    def snapshot_all(self, now: Optional[str] = None) -> Dict[str, dict]:
        return {task_id: self.snapshot(task_id, now) for task_id in self._tasks}

    def diagnose(self, task_id: str, now: Optional[str] = None) -> str:
        snap = self.snapshot(task_id, now)
        evidence = snap["evidence"]
        seen = f"{evidence['type']} seq {evidence['seq']}" if evidence else "none"
        text = (f"{snap['task_id']}: {snap['state']} ({snap['reason']}) — "
                f"{snap['reason_text']} Last evidence: {seen}.")
        if snap["stale"]:
            text += f" STALE ({snap['stale_why']})."
        if snap["gap"] is not None:
            text += f" Sequence gap from {snap['gap']}: reconnect to catch up."
        return text

    def pop_pulses(self) -> list:
        pulses, self._pulses = self._pulses, []
        return pulses

    # -- internals --------------------------------------------------------
    def _replay_one(self, event: Any, source: str) -> dict:
        event_id = _get(event, "event_id")
        if event_id is not None and event_id in self._seen_event_ids:
            task_id = _get(event, "task_id")
            if task_id is not None:
                self._tasks.setdefault(str(task_id),
                                       _new_record(str(task_id)))["duplicate_count"] += 1
            return {"result": "duplicate", "task_id": task_id,
                    "event_id": event_id}
        return self._apply(event, source, allow_pulse=False)

    def _drain_pending(self) -> None:
        while self._cursor + 1 in self._pending:
            self._cursor += 1
            for event, source in self._pending.pop(self._cursor):
                self._apply(event, source)
        if not self._pending:
            self._gap_from = None

    def _apply(self, event: Any, source: str, allow_pulse: bool = True) -> dict:
        if source == "replay":
            allow_pulse = False
        event_id = _get(event, "event_id")
        if event_id is not None:
            if event_id in self._seen_event_ids:
                task_id = _get(event, "task_id")
                if task_id is not None:
                    rec = self._tasks.setdefault(str(task_id),
                                                 _new_record(str(task_id)))
                    rec["duplicate_count"] += 1
                return {"result": "duplicate", "task_id": task_id,
                        "event_id": event_id}
            self._seen_event_ids.add(event_id)
        dedupe_key = _get(event, "dedupe_key")
        if dedupe_key is not None:
            content = self._content_of(event)
            prior = self._seen_effects.get(dedupe_key)
            if prior is not None:
                task_id = _get(event, "task_id")
                if prior == content:
                    if task_id is not None:
                        self._tasks.setdefault(str(task_id), _new_record(
                            str(task_id)))["duplicate_count"] += 1
                    return {"result": "duplicate", "task_id": task_id,
                            "dedupe_key": dedupe_key}
                if task_id is not None:
                    rec = self._tasks.setdefault(str(task_id),
                                                 _new_record(str(task_id)))
                    rec["conflict_count"] += 1
                    self._set_unknown(
                        rec, event, "dedupe-conflict",
                        f"Dedupe key {dedupe_key!r} reused with different "
                        "content; prior state kept.")
                return {"result": "conflict", "task_id": task_id,
                        "dedupe_key": dedupe_key}
            self._seen_effects[dedupe_key] = content
        task_id = _get(event, "task_id")
        if task_id is None:
            return {"result": "system", "type": _etype(event)}
        rec = self._tasks.setdefault(str(task_id), _new_record(str(task_id)))
        self._fold(rec, event)
        if rec["state"] in _PULSE_STATES and allow_pulse:
            self._pulses.append({"task_id": rec["task_id"], "state": rec["state"],
                                 "event_id": event_id,
                                 "seq": _get(event, "seq")})
        return {"result": "applied", "task_id": rec["task_id"],
                "state": rec["state"], "event_id": event_id}

    @staticmethod
    def _content_of(event: Any) -> tuple:
        payload = _payload(event)
        items = tuple(sorted((str(k), str(v)) for k, v in payload.items()))
        return (_etype(event), str(_get(event, "task_id")),
                str(_get(event, "attempt")), str(_get(event, "dispatch_id")),
                str(_get(event, "worker_id")), str(_get(event, "result_id")),
                items)

    def _track(self, rec: dict, event: Any, note: Optional[str] = None) -> None:
        rec["history_len"] += 1
        at = _get(event, "ts_utc")
        if isinstance(at, str) and at:
            last = rec["last_at"]
            if last is None or at > last:
                rec["last_at"] = at
            elif at < last:
                rec["late_count"] += 1
        if note:
            rec["notes"].append(note)

    def _set_unknown(self, rec: dict, event: Any, reason: str,
                     text: str) -> None:
        rec["state"] = "UNKNOWN"
        rec["reason"] = reason
        rec["reason_text"] = text
        rec["evidence"] = self._evidence_of(event)
        self._track(rec, event, f"UNKNOWN: {reason}")

    @staticmethod
    def _evidence_of(event: Any) -> dict:
        return {"event_id": _get(event, "event_id"), "seq": _get(event, "seq"),
                "type": _etype(event), "at": _get(event, "ts_utc"),
                "source": "courier journal (courier.db)"}

    def _set_state(self, rec: dict, event: Any, state: str, reason: str,
                   text: str) -> None:
        rec["state"] = state
        rec["reason"] = reason
        rec["reason_text"] = text
        rec["evidence"] = self._evidence_of(event)
        self._track(rec, event)

    def _fold(self, rec: dict, event: Any) -> None:
        kind = _etype(event)
        if kind == "TASK_CREATED":
            depends = _payload(event).get("depends_on")
            rec["depends_on"] = depends
            rec["attempt"] = 0
            if depends is None or depends in self._verified_done:
                self._set_state(rec, event, "READY", "created-claimable",
                                "Created and claimable.")
            else:
                self._set_state(rec, event, "QUEUED", "waiting-on-dependency",
                                f"Created; waits for verified completion of {depends}.")
            return
        if rec["history_len"] == 0 and rec["evidence"] is None:
            self._set_unknown(rec, event, "missing-creation-evidence",
                              f"{kind} without a prior TASK_CREATED; no handover assumed.")
            return
        handler = getattr(self, f"_on_{kind.lower()}", None)
        if handler is None:
            if kind in ("TASK_PROGRESS", "TASK_CANCEL_REQUESTED",
                        "LATE_RESULT_DISCARDED", "CONTROLLER_STARTED",
                        "CONTROLLER_STOPPED"):
                self._track(rec, event, f"noted {kind}; state unchanged")
            else:
                self._set_unknown(rec, event, "unknown-event-type",
                                  f"Event type {kind!r} is not part of the bridge contract.")
            return
        handler(rec, event)

    # -- per-type transitions ---------------------------------------------
    def _on_task_claimed(self, rec: dict, event: Any) -> None:
        attempt, dispatch, worker = (_get(event, "attempt"),
                                     _get(event, "dispatch_id"),
                                     _get(event, "worker_id"))
        if rec["state"] not in ("QUEUED", "READY"):
            self._set_unknown(rec, event, "claim-out-of-order",
                              "Claim arrived while the task was not queued; "
                              "no handover assumed.")
            return
        if not isinstance(attempt, int) or attempt != rec["attempt"] + 1:
            self._set_unknown(rec, event, "claim-fence",
                              "Claim attempt is not the next attempt; no handover assumed.")
            return
        if not dispatch or not worker:
            self._set_unknown(rec, event, "claim-fence",
                              "Claim lacks dispatch_id or worker_id; no handover assumed.")
            return
        rec["attempt"] = attempt
        rec["dispatch_id"] = dispatch
        rec["worker_id"] = worker
        self._set_state(rec, event, "TRANSFERRED", "claimed-awaiting-start",
                        f"Ledger handed attempt {attempt} to {worker}; worker start not yet evidenced.")

    def _on_task_started(self, rec: dict, event: Any) -> None:
        if rec["state"] != "TRANSFERRED":
            self._set_unknown(rec, event, "missing-handover-evidence",
                              "Start without an evidenced claim handover; not shown as running.")
            return
        if (_get(event, "attempt") != rec["attempt"]
                or _get(event, "dispatch_id") != rec["dispatch_id"]):
            self._set_unknown(rec, event, "start-fence",
                              "Start does not name the claimed dispatch; not shown as running.")
            return
        self._set_state(rec, event, "RUNNING", "worker-started",
                        "Worker start evidenced for the claimed dispatch.")

    def _on_result_ready(self, rec: dict, event: Any) -> None:
        if rec["state"] != "RUNNING":
            self._set_unknown(rec, event, "missing-handover-evidence",
                              "Result without an evidenced running attempt; "
                              "not shown as verifying.")
            return
        if (_get(event, "attempt") != rec["attempt"]
                or _get(event, "dispatch_id") != rec["dispatch_id"]
                or not _get(event, "result_id")):
            self._set_unknown(rec, event, "result-fence",
                              "Result does not name the running dispatch and result; "
                              "not shown as verifying.")
            return
        payload = _payload(event)
        if not _has_handover_artifacts(payload) or payload.get("outcome") not in _OUTCOMES:
            self._set_unknown(rec, event, "result-evidence",
                              "Result lacks artifacts or a known outcome; not shown as verifying.")
            return
        rec["pending_result_id"] = _get(event, "result_id")
        self._set_state(rec, event, "VERIFYING", "result-awaiting-verdict",
                        "Result handed to the verifier; verdict not yet evidenced.")

    def _on_result_accepted(self, rec: dict, event: Any) -> None:
        if rec["state"] != "VERIFYING":
            self._set_unknown(rec, event, "verdict-without-verifying",
                              "Acceptance without an evidenced verifying result; not green.")
            return
        if _get(event, "result_id") != rec["pending_result_id"]:
            self._set_unknown(rec, event, "verdict-fence",
                              "Acceptance names another result; not green.")
            return
        if not _has_verifier_identity(_payload(event)):
            self._set_unknown(rec, event, "verifier-evidence-missing",
                              "Acceptance lacks verifier identity; not green.")
            return
        rec["accepted_result_id"] = _get(event, "result_id")
        rec["pending_result_id"] = None
        rec["verifier"] = _payload(event)["verifier"]
        self._set_state(rec, event, "VERIFIED", "verifier-accepted",
                        "Verifier accepted the result; completion not yet evidenced.")

    def _on_result_rejected(self, rec: dict, event: Any) -> None:
        self._set_unknown(rec, event, "rejected-awaiting-decision",
                          "Result rejected; scheduler decision not yet evidenced.")

    def _on_task_complete(self, rec: dict, event: Any) -> None:
        if rec["state"] != "VERIFIED":
            self._set_unknown(rec, event, "completion-without-verdict",
                              "Completion without an evidenced verifier verdict; not done.")
            return
        if (_get(event, "result_id") != rec["accepted_result_id"]
                or rec["verifier"] is None):
            self._set_unknown(rec, event, "completion-evidence",
                              "Completion does not name the accepted result with "
                              "verifier evidence; not done.")
            return
        self._set_state(rec, event, "DONE", "verifier-completed",
                        "Valid completion proof: accepted result completed.")
        self._verified_done.add(rec["task_id"])
        self._promote_waiters(rec["task_id"])

    def _promote_waiters(self, done_task_id: str) -> None:
        for other in self._tasks.values():
            if (other["state"] == "QUEUED" and other["depends_on"] == done_task_id):
                other["state"] = "READY"
                other["reason"] = "dependency-verified"
                other["reason_text"] = (
                    f"Dependency {done_task_id} completed verified; now claimable.")
                other["notes"].append("READY: dependency-verified")

    def _on_task_retry_scheduled(self, rec: dict, event: Any) -> None:
        rec["pending_result_id"] = None
        self._set_state(rec, event, "QUEUED", "retry-scheduled",
                        "Scheduler re-queued the attempt.")

    def _on_retry_authorized(self, rec: dict, event: Any) -> None:
        rec["pending_result_id"] = None
        self._set_state(rec, event, "QUEUED", "retry-authorized",
                        "Human authorised one more attempt.")

    def _on_lease_expired(self, rec: dict, event: Any) -> None:
        self._set_unknown(rec, event, "lease-lost-awaiting-decision",
                          "Lease lost with uncertain outcome; scheduler decision "
                          "not yet evidenced.")

    def _on_task_blocked(self, rec: dict, event: Any) -> None:
        self._set_state(rec, event, "BLOCKED", "blocked",
                        f"Scheduler blocked the task: {_payload(event).get('reason') or 'see journal'}.")

    def _on_task_failed(self, rec: dict, event: Any) -> None:
        self._set_state(rec, event, "FAILED", "failed",
                        f"Scheduler failed the task: {_payload(event).get('reason') or 'see journal'}.")

    def _on_task_cancelled(self, rec: dict, event: Any) -> None:
        self._set_unknown(rec, event, "cancelled",
                          "Task cancelled; the bridge shows no invented terminal state.")

    def _on_effect_confirmed(self, rec: dict, event: Any) -> None:
        self._set_unknown(rec, event, "human-confirmed-not-verified",
                          "Human confirmed the effect; Courier did not verify it — "
                          "never shown as done or green.")

    # -- staleness ----------------------------------------------------------
    def _stale_of(self, rec: dict, now: str) -> Tuple[bool, Optional[str]]:
        moment = _parse_stamp(now)
        if moment is None:
            return False, None
        last = _parse_stamp(rec["last_at"])
        if last is not None and (moment - last).total_seconds() > self.stale_after_s:
            return True, f"no evidenced event for {(moment - last).total_seconds():.0f}s"
        beat = _parse_stamp(rec["heartbeat_at"])
        if beat is not None and rec["heartbeat_alive"] is False:
            return True, "worker heartbeat reports not alive"
        if (beat is not None and rec["heartbeat_alive"]
                and (moment - beat).total_seconds() > self.stale_after_s):
            return True, "worker heartbeat expired"
        return False, None
