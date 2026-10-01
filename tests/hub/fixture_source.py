"""Builds the desktop fixture from the real projection model (lane L5).

tests/desktop/fixtures/home_view.json is what hub_core.mjs is tested against;
test_hub_fixture.py fails if the model and the fixture drift apart.
"""

from courier_core.events import Event, EventType
from courier_core.state_machine import TaskState, TaskStatus
from courier_hub import model

TS = "2026-10-02T08:00:00.000000Z"


def _state(task_id, status, **kw):
    base = dict(task_id=task_id, status=TaskStatus(status), adapter="synthetic", params={},
                effect_class="non_idempotent", max_attempts=3, lease_ttl_s=6, timeout_s=None, attempt=1)
    base.update(kw)
    return TaskState(**base)


def _ev(task_id, kind, **payload):
    return Event(type=kind, task_id=task_id, payload=payload, event_id=f"e-{task_id}-{kind.value}", ts_utc=TS)


def build():
    tasks = [
        _state("t-blocked", "BLOCKED"),
        _state("t-running", "RUNNING"),
        _state("t-verified", "COMPLETE", resolution="verified"),
        _state("t-human", "COMPLETE", resolution="effect_confirmed", decided_by="desktop:ana"),
        _state("t-uncertain", "CANCELLED", resolution="cancelled_effect_unknown", decided_by="desktop:ana"),
        _state("t-failed", "FAILED"),
    ]
    events = {t.task_id: [_ev(t.task_id, EventType.TASK_CREATED, adapter="synthetic", params={},
                              effect_class="non_idempotent", max_attempts=3, lease_ttl_s=6)] for t in tasks}
    view = model.home(tasks, events)
    view.update({"status": {"controller": "running", "checked_at": TS}, "truth": "ok", "head_seq": 12,
                 "read_at": TS})
    return view
