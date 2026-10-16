"""Test automatic restart resume across controller restart and crash before attribution.

Mission:
Courier arbeitet nach Neustart am richtigen Punkt weiter.
1. Scenario 1 (Normal Restart Resume):
   A wird ausgeführt und dauerhaft akzeptiert.
   Controller wird kontrolliert gestoppt und neu gestartet.
   Courier erkennt A als abgeschlossen und fährt mit B fort.
2. Scenario 2 (Crash before Result Attribution / Uncertain Non-Idempotent Work):
   Der Prozess / Worker endet nach Ausführung, aber bevor das Resultat eindeutig zugeordnet werden konnte.
   In diesem Fall gilt bei non-idempotenter Arbeit LEASE_EXPIRED:restart_grace gefolgt von TASK_BLOCKED
   (Human Action / Reconcile Required), NIEMALS blind erneute externe Ausführung.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from courier_core.controller import Controller
from courier_core.events import EventType
from courier_core.state_machine import TaskStatus
from scripts.coordination_ledger import (
    AgentID,
    CoordinationEvent,
    EventType as LedgerEventType,
    HostID,
    MissionStatus,
)
from scripts.coordination_resume import discover_resumable, reduce_store
from scripts.github_coordination import FileCoordinationStore

REPO = Path(__file__).resolve().parents[1]
AGENT = "GOOGLE_WINDOWS"
HOST = "WINDOWS_REMOTE"
GOAL_ID = "goal.restart.resume"
GOAL_FP = "11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff"


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def pass_time(ctl, clock, seconds, step=0.25):
    elapsed = 0.0
    while elapsed < seconds:
        clock.advance(step)
        elapsed += step
        ctl.tick()


def _courier_cls():
    path = REPO / "tests" / "golden" / "golden_harness.py"
    spec = importlib.util.spec_from_file_location("restart_golden_harness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Courier


def _event(eid, mid, ts, deps=None):
    return CoordinationEvent(
        event_id=eid,
        mission_id=mid,
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=LedgerEventType.ASSIGNED,
        status=MissionStatus.WORKING,
        depends_on=deps or [],
        head="sha",
        evidence_ref="ref",
        created_at=ts,
        payload_hash="h",
        ownership=AGENT,
    )


def _spec(content_unit):
    return {
        "adapter": "synthetic",
        "params": {
            "sleep_s": 0,
            "write": "out.txt",
            "content": content_unit,
            "hang": False,
            "fail_transient_n": 0,
            "fault_attempts": [1],
        },
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
        "goal_id": GOAL_ID,
        "goal_fingerprint": GOAL_FP,
    }


def _bridge(home, url):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.ledger_v1_bridge",
            "--home",
            str(home),
            "--agent-id",
            AGENT,
            "--host-id",
            HOST,
            "--controller",
            url,
        ],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )


def _wait_complete(courier, task_id, timeout=25):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        response = courier.api.get(f"/v1/tasks/{task_id}", timeout=5)
        if response.status_code == 200:
            last = response.json()
            if last.get("status") == "COMPLETE":
                return last
            if last.get("status") in ("FAILED", "CANCELLED", "BLOCKED"):
                raise AssertionError(f"Task {task_id} unexpected status: {last}")
        time.sleep(0.2)
    raise AssertionError(f"Timeout waiting for task {task_id} to be COMPLETE; last={last}")


def test_restart_resume_after_a_completes(tmp_path):
    """Scenario 1: Controller restarts after A is accepted; B proceeds cleanly."""
    Courier = _courier_cls()
    home = tmp_path / "home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()

    courier = Courier(home, logs)
    try:
        courier.start_controller(timeout=20)
        store = FileCoordinationStore(home / "coordination_ledger.jsonl")
        store.write_event(_event("a-assign", "A", "2026-10-11T13:00:00Z"))
        store.write_event(_event("b-assign", "B", "2026-10-11T13:00:01Z", deps=["A"]))

        (home / "ledger_tasks.json").write_text(
            json.dumps({"A": _spec("content-a"), "B": _spec("content-b")}), encoding="utf-8"
        )

        # 1. Dispatch A
        res1 = _bridge(home, courier.base_url)
        assert res1.returncode == 0, res1.stderr
        created = [e for e in courier.all_events() if e["type"] == "TASK_CREATED"]
        assert len(created) == 1
        task_a = created[0]["task_id"]

        # 2. Worker executes A to COMPLETE
        worker_a = courier.start_worker()
        view_a = _wait_complete(courier, task_a)
        courier.stop_worker_graceful(worker_a, timeout=15)
        assert view_a["status"] == "COMPLETE"
        assert view_a["accepted_result_id"]

        # 3. Controlled restart of the test-controller
        courier.stop_controller_graceful(timeout=10)
        assert courier.controller.poll() is not None

        # Start controller again in fresh process
        courier.start_controller(timeout=20)

        # Verify A is still recognized as COMPLETE by restarted controller
        view_a_restarted = courier.api.get(f"/v1/tasks/{task_a}", timeout=5).json()
        assert view_a_restarted["status"] == "COMPLETE"
        assert view_a_restarted["accepted_result_id"] == view_a["accepted_result_id"]

        # 4. Bridge resumes after restart: reconciles A and automatically posts B
        res2 = _bridge(home, courier.base_url)
        assert res2.returncode == 0, res2.stderr

        # Check ledger reconciled A
        reducer = reduce_store(store)
        finals = [e for e in reducer.events if e.event_type == LedgerEventType.FINAL]
        assert len(finals) == 1
        assert finals[0].mission_id == "A"

        # Check B is now posted to restarted controller
        created_events = [e for e in courier.all_events() if e["type"] == "TASK_CREATED"]
        assert len(created_events) == 2
        task_b = next(e["task_id"] for e in created_events if e["task_id"] != task_a)

        # 5. Worker executes B to COMPLETE
        worker_b = courier.start_worker()
        view_b = _wait_complete(courier, task_b)
        courier.stop_worker_graceful(worker_b, timeout=15)
        assert view_b["status"] == "COMPLETE"

        # Bridge reconciles B
        res3 = _bridge(home, courier.base_url)
        assert res3.returncode == 0, res3.stderr

        reducer_final = reduce_store(store)
        all_finals = {e.mission_id for e in reducer_final.events if e.event_type == LedgerEventType.FINAL}
        assert all_finals == {"A", "B"}
    finally:
        courier.close()


def test_crash_before_result_attribution_enters_blocked(tmp_path):
    """Scenario 2: Process dies after execution but before result attribution.

    Non-idempotent task must enter BLOCKED (reconcile / human required)
    and NOT be blindly re-executed.
    """
    home = tmp_path / "home_crash"
    home.mkdir()

    # 1. Controller 1 starts with FakeClock, creates non-idempotent task
    clock1 = FakeClock(start=100.0)
    ctl = Controller(home, clock=clock1).boot()
    body = {
        "adapter": "synthetic",
        "params": {"write": "pay.txt", "content": "100EUR"},
        "effect_class": "non_idempotent",
        "max_attempts": 2,
        "lease_ttl_s": 5,
    }
    task_res = ctl.create_task(body)
    task_id = task_res[1]["task_id"]

    # Claim & start attempt 1
    lease = ctl.claim({"worker_id": "worker-crashed"})
    dispatch_id = lease["dispatch_id"]
    ctl.start({"dispatch_id": dispatch_id, "worker_id": "worker-crashed"})

    # Worker executes external effect, then dies/crashes before result attribution!
    ctl._stopping.set()
    ctl.journal.close()

    # 2. Restart controller after the crash with fresh FakeClock
    clock2 = FakeClock(start=500.0)
    restarted_ctl = Controller(home, clock=clock2).boot()
    try:
        # On boot, recovery places the open lease into restart_grace window
        t_state = restarted_ctl.journal.task(task_id)
        assert t_state.status is TaskStatus.RUNNING
        assert t_state.attempt == 1

        # Advance time past lease_ttl_s (5s) to trigger restart_grace expiry
        pass_time(restarted_ctl, clock2, 7.0)

        # Check state: lease expired with reason 'restart_grace'
        events = [e for e in restarted_ctl.journal.events(task_id=task_id)]
        event_types = [e.type.value for e in events]

        assert "LEASE_EXPIRED" in event_types
        expired_event = next(e for e in events if e.type.value == "LEASE_EXPIRED")
        assert expired_event.payload.get("reason") == "restart_grace"

        # CRITICAL SAFETY CHECK:
        # Non-idempotent task with uncertain outcome MUST enter BLOCKED (RECONCILE REQUIRED),
        # NEVER TASK_RETRY_SCHEDULED!
        updated_state = restarted_ctl.journal.task(task_id)
        assert updated_state.status is TaskStatus.BLOCKED
        assert "TASK_BLOCKED" in event_types
        assert "TASK_RETRY_SCHEDULED" not in event_types

        # Verify that no worker can claim this task for blind re-execution
        new_claim = restarted_ctl.claim({"worker_id": "worker-new"})
        assert new_claim is None, "BLOCKED task must not be claimed for re-execution"

    finally:
        restarted_ctl.stop()
