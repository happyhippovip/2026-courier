"""P9 hardening stub for courier_core.verification (fail-closed verifier hand-off)."""

from courier_core.state_machine import TaskStatus, TaskState
from courier_core.verification import Verdict


def _task(**changes):
    value = dict(task_id="t1", status=TaskStatus.VERIFYING, adapter="synthetic",
                 params={}, effect_class="idempotent", max_attempts=3,
                 lease_ttl_s=6, timeout_s=None)
    value.update(changes)
    return TaskState(**value)


def test_claim_stub_verdict_shape():
    task = _task()
    assert task.adapter == "synthetic"
    assert Verdict(True).accepted is True
