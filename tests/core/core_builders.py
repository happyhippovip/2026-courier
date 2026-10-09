"""Event builders for the L2 invariant suite (tests/core)."""

import hashlib
import itertools

from courier_core.events import Event, EventType

SHA = hashlib.sha256(b"courier-golden").hexdigest()
_counter = itertools.count(1)


def stable(**fields):
    """Deterministic event_id / ts_utc so independent journals can be compared."""
    n = next(_counter)
    fields.setdefault("event_id", f"evt-{n:06d}")
    fields.setdefault("ts_utc", f"2026-10-01T00:00:{n % 60:02d}.000000Z")
    return fields


def created(task_id="t1", effect_class="idempotent", max_attempts=3, lease_ttl_s=6, **extra):
    payload = {"adapter": "synthetic", "params": {"sleep_s": 1}, "effect_class": effect_class,
               "max_attempts": max_attempts, "lease_ttl_s": lease_ttl_s, **extra}
    return Event(**stable(type=EventType.TASK_CREATED, task_id=task_id, payload=payload))


class Attempt:
    """Events of one attempt, fenced by its own dispatch_id."""

    def __init__(self, task_id="t1", attempt=1, worker_id="w1"):
        self.task_id, self.attempt, self.worker_id = task_id, attempt, worker_id
        self.dispatch_id = f"d-{task_id}-{attempt}"
        self.result_id = f"r-{task_id}-{attempt}"

    def _ev(self, event_type, **kw):
        base = dict(type=event_type, task_id=self.task_id, attempt=self.attempt, dispatch_id=self.dispatch_id)
        base.update(kw)
        return Event(**stable(**base))

    def claimed(self):
        return self._ev(EventType.TASK_CLAIMED, worker_id=self.worker_id, payload={"ttl_s": 6})

    def started(self):
        return self._ev(EventType.TASK_STARTED, worker_id=self.worker_id)

    def progress(self, message="working"):
        return self._ev(EventType.TASK_PROGRESS, payload={"message": message})

    def result_ready(self, outcome="success", sha=SHA, result_id=None):
        return self._ev(EventType.RESULT_READY, worker_id=self.worker_id, result_id=result_id or self.result_id,
                        payload={"artifacts": [{"path": "out.txt", "sha256": sha}], "outcome": outcome})

    def accepted(self):
        return self._ev(EventType.RESULT_ACCEPTED, result_id=self.result_id)

    def rejected(self, retryable=True, reason="provider transient error"):
        return self._ev(EventType.RESULT_REJECTED, result_id=self.result_id,
                        payload={"reason": reason, "retryable": retryable})

    def complete(self):
        return self._ev(EventType.TASK_COMPLETE, result_id=self.result_id)

    def lease_expired(self, reason="ttl"):
        return self._ev(EventType.LEASE_EXPIRED, worker_id=self.worker_id, payload={"reason": reason})

    def retry_scheduled(self):
        return Event(**stable(type=EventType.TASK_RETRY_SCHEDULED, task_id=self.task_id, attempt=self.attempt,
                              payload={"reason": "retry"}))

    def late_result(self):
        return Event(**stable(type=EventType.LATE_RESULT_DISCARDED, task_id=self.task_id,
                              dispatch_id=self.dispatch_id, result_id=f"late-{self.result_id}",
                              payload={"reason": "superseded dispatch"}))

    def happy(self):
        return [self.claimed(), self.started(), self.result_ready(), self.accepted(), self.complete()]


def task_event(event_type, task_id="t1", **payload):
    return Event(**stable(type=event_type, task_id=task_id, payload=payload))


def golden_path(task_id="t1"):
    return [created(task_id), *Attempt(task_id, 1).happy()]


def transient_twice_then_success(task_id="t2"):
    events = [created(task_id, max_attempts=3)]
    for n in (1, 2):
        a = Attempt(task_id, n)
        events += [a.claimed(), a.started(), a.result_ready(outcome="failure"), a.rejected(), a.retry_scheduled()]
    return events + Attempt(task_id, 3).happy()


def worker_killed_then_retried(task_id="t3"):
    """Started lease loss stops. The name is historical; the attempt is not retried."""
    first = Attempt(task_id, 1)
    return [created(task_id), first.claimed(), first.started(), first.lease_expired(),
            task_event(EventType.TASK_BLOCKED, task_id=task_id, reason="outcome unknown"),
            first.late_result()]


def mixed_history():
    """Several tasks, interleaved, including system events."""
    controller = Event(**stable(type=EventType.CONTROLLER_STARTED))
    a, b, c = golden_path("ta"), transient_twice_then_success("tb"), worker_killed_then_retried("tc")
    merged = [controller]
    for trio in itertools.zip_longest(a, b, c):
        merged += [e for e in trio if e is not None]
    return merged
