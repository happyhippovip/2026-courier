import pytest
from pathlib import Path
from tests.controller.ctrl_helpers import FakeClock, make_controller, task_body, result_body
from courier_core.controller import NORMAL, DEGRADED, ApiError
from courier_core.projection import projection_hash
from courier_core.state_machine import TaskStatus


def test_controller_double_start_idempotent(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    assert ctl.mode == NORMAL
    # Calling start or tick repeatedly while running should not crash
    ctl.tick()
    ctl.tick()
    ctl.stop()


def test_task_claim_with_zero_admissible_tasks(tmp_path):
    home = tmp_path / "home"
    ctl = make_controller(home)
    # No tasks created; claim returns None
    claimed = ctl.claim({"worker_id": "idle-worker"})
    assert claimed is None
    ctl.stop()


def test_task_completion_lifecycle_with_verifier_receipt(tmp_path):
    home = tmp_path / "home"
    clock = FakeClock()
    ctl = make_controller(home, clock=clock)

    # 1. Create Task
    _, task_data = ctl.create_task(task_body(lease_ttl_s=30))
    task_id = task_data["task_id"]

    # 2. Claim Lease
    lease = ctl.claim({"worker_id": "worker-42"})
    assert lease is not None
    assert lease["task_id"] == task_id
    dispatch_id = lease["dispatch_id"]

    # 3. Mark Started
    ctl.start({"dispatch_id": dispatch_id})
    clock.advance(5.0)

    # 4. Submit Result
    res = ctl.result(result_body(dispatch_id, outcome="success"))
    assert res is not None

    # Drain verifiers
    ctl.drain()

    # 5. Check projection state
    t = ctl.journal.task(task_id)
    assert t.status == TaskStatus.COMPLETE
    ctl.stop()


def test_heartbeat_extends_live_lease(tmp_path):
    home = tmp_path / "home"
    clock = FakeClock()
    ctl = make_controller(home, clock=clock)

    _, task_data = ctl.create_task(task_body(lease_ttl_s=10))
    lease = ctl.claim({"worker_id": "long-runner"})
    dispatch_id = lease["dispatch_id"]
    ctl.start({"dispatch_id": dispatch_id})

    # Advance 4 seconds (within 10s TTL)
    clock.advance(4.0)
    ctl.tick()

    # Heartbeat refreshes the lease
    hb = ctl.heartbeat({"worker_id": "long-runner", "dispatch_ids": [dispatch_id]})
    assert hb is not None
    assert hb["stop"] == []

    # Advance another 4 seconds
    clock.advance(4.0)
    ctl.tick()

    # Worker still owns dispatch and is running
    t = ctl.journal.task(task_data["task_id"])
    assert t.status == TaskStatus.RUNNING
    ctl.stop()
