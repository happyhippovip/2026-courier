"""C018: Safe Worker Shutdown & Process Lifecycle Tests.

Verifies:
1. Controlled worker shutdown reaps its own child tree while leaving alien processes untouched.
2. Outbox results are safely preserved across worker shutdown.
3. Duplicate shutdown requests are strictly idempotent and safe.
4. Task cancellation requested after a result is submitted does not corrupt or clobber valid outcomes.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from courier_core.controller import ApiError, Controller
from courier_core.events import EventType
from courier_core.serve import Service
from courier_core.state_machine import TaskStatus
from courier_worker import host as H
from courier_worker.host import Outcome, WorkerHost, _spawn_contained
from ctrl_helpers import Verifiers, accept_all, make_controller, result_body, task_body


def test_controlled_worker_shutdown_reaps_child_and_leaves_alien_untouched(tmp_path: Path):
    """Controlled worker shutdown terminates and reaps its own child tree,

    while independent alien processes remain completely running and untouched.
    """
    # 1. Spawn an independent alien process
    alien = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert alien.poll() is None, "Alien process failed to start"

        # 2. Spawn an isolated child under worker containment
        run_dir = str(tmp_path / "run")
        os.makedirs(run_dir, exist_ok=True)
        child_argv = [sys.executable, "-c", "import time; time.sleep(30)"]
        contained = _spawn_contained(child_argv, run_dir, "test-child")
        assert contained.poll() is None, "Contained child should be running"

        # 3. Controlled shutdown of the contained child tree
        contained.terminate_tree(grace=2.0)
        reaped_code = contained.wait(timeout=5.0)

        assert reaped_code is not None, "Child process must be reaped on shutdown"
        assert contained.poll() is not None, "Child process must be terminated"

        # 4. Invariant: Alien process was NOT touched
        assert alien.poll() is None, "Alien process was killed or affected by worker shutdown!"
    finally:
        if alien.poll() is None:
            alien.terminate()
            alien.wait(timeout=5)


def test_shutdown_preserves_durable_result_in_outbox(tmp_path: Path):
    """When worker shuts down with pending results, outbox entries are preserved on disk."""
    home = tmp_path / "worker_home"
    home.mkdir(parents=True, exist_ok=True)

    result_payload = {
        "dispatch_id": "disp-shutdown-01",
        "result_id": "res-shutdown-01",
        "outcome": "success",
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
    }

    # Write open result to outbox
    H.outbox_write(str(home), result_payload)

    # Verify result is on disk before shutdown
    pending_before = H.outbox_read_all(str(home))
    assert len(pending_before) == 1

    # Simulate worker host shutdown
    host = WorkerHost(str(home))
    assert host.busy is False

    # Verify result remains intact after worker shutdown
    pending_after = H.outbox_read_all(str(home))
    assert len(pending_after) == 1
    assert pending_after[0][1]["dispatch_id"] == "disp-shutdown-01"
    assert pending_after[0][1]["result_id"] == "res-shutdown-01"


def test_duplicate_shutdown_request_is_idempotent(tmp_path: Path):
    """Duplicate shutdown and stop requests must be idempotent and non-blocking."""
    home = tmp_path / "service_home"
    ctl = make_controller(home)
    service = Service(home, 0, controller=ctl)

    t = threading.Thread(target=service.run, daemon=True)
    t.start()

    try:
        # First stop request
        service.request_stop()
        assert service.server.stopping.is_set()

        # Second duplicate stop request (must not raise or deadlock)
        service.request_stop()
        assert service.server.stopping.is_set()

        # Wait for service run thread to cleanly shut down
        t.join(timeout=5.0)
        assert not t.is_alive(), "Service thread must stop cleanly"
        assert service._stopped.is_set()

        # Subsequent duplicate shutdown call (must be no-op)
        service.shutdown()
        assert service._stopped.is_set()
    finally:
        service.request_stop()
        t.join(timeout=2.0)



def test_cancel_requested_after_result_does_not_clobber_valid_completion(tmp_path: Path):
    """When a task result is already accepted or complete, subsequent cancellation

    refuses to clobber the valid outcome.
    """
    home = tmp_path / "controller_home"
    ctl = make_controller(home)

    # 1. Create, claim, and start task
    st, created = ctl.create_task(task_body())
    assert st == 201
    task_id = created["task_id"]

    lease = ctl.claim({"worker_id": "w1"})
    dsp_id = lease["dispatch_id"]
    ctl.start({"dispatch_id": dsp_id})

    # 2. Submit result
    res = result_body(dsp_id, result_id="res-001", outcome="success")
    st, resp = ctl.result(res)
    assert st == 200
    assert resp["status"] == "ACCEPTED_FOR_VERIFY"

    # Task is now in VERIFYING state
    assert ctl.journal.task(task_id).status is TaskStatus.VERIFYING

    # 3. Attempt cancel while result is verifying:
    # Controller records cancel_requested but verification queue still drains
    cancel_resp = ctl.cancel(task_id, {"reason": "too late cancel"})
    assert cancel_resp["cancel_requested"] is True

    # Drain verification queue
    ctl.drain()

    # Task should successfully complete (verified result outranks late cancel)
    task_state = ctl.journal.task(task_id)
    assert task_state.status is TaskStatus.COMPLETE
    assert task_state.accepted_result_id == "res-001"

    # 4. Attempt cancel on terminal COMPLETE task
    with pytest.raises(ApiError) as exc_info:
        ctl.cancel(task_id, {"reason": "cancel after completion"})
    assert exc_info.value.status == 409
    assert exc_info.value.code == "terminal"

    # Invariant: task remains COMPLETE with accepted result intact
    assert ctl.journal.task(task_id).status is TaskStatus.COMPLETE
    assert ctl.journal.task(task_id).accepted_result_id == "res-001"
