"""Deterministic Two-Task Workflow (A -> B Automatic Dispatch).

Mission: Eine abgeschlossene Aufgabe A macht B automatisch ausführbar.
Workflow:
1. Task A erzeugt ein überprüfbares Testartefakt (synthetic adapter: out.txt mit SHA256).
2. Unabhängiger Verifier (courier_core.verification + synthetic.verify) bestätigt A.
3. Das Ledger reconciled A (ledger_v1_bridge._feedback + coordination_ledger write_event FINAL).
4. Task B wird READY (coordination_resume.discover_resumable).
5. Der vorhandene Dispatcher startet B ohne menschliche Relay-Nachricht.

Metrics measured:
- HUMAN_RELAY_COUNT
- A_EXECUTION_COUNT
- B_EXECUTION_COUNT
- Start- und Endzeit
- Tatsächliche Resultatbelege (Artifact hash, accepted_result_id, ledger event_id)
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

from scripts.coordination_ledger import (
    AgentID,
    CoordinationEvent,
    EventType,
    HostID,
    MissionStatus,
)
from scripts.coordination_resume import discover_resumable, reduce_store
from scripts.github_coordination import FileCoordinationStore

REPO = Path(__file__).resolve().parents[1]
AGENT = "GOOGLE_WINDOWS"
HOST = "WINDOWS_REMOTE"
GOAL_ID = "goal.bridge.ab.autonomous"
GOAL_FP = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _courier_cls():
    path = REPO / "tests" / "golden" / "golden_harness.py"
    spec = importlib.util.spec_from_file_location("ledger_bridge_golden_harness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Courier


def _event(eid, mid, ts, deps=None):
    return CoordinationEvent(
        event_id=eid,
        mission_id=mid,
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED,
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


def _run_bridge(home, url):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
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
    return proc


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
                raise AssertionError(f"Task {task_id} failed unexpectedly: {last}")
        time.sleep(0.2)
    raise AssertionError(f"Timeout waiting for task {task_id} to be COMPLETE; last={last}")


def test_automatic_a_to_b_dispatch_workflow(tmp_path):
    start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    start_time = time.time()

    human_relay_count = 0
    a_execution_count = 0
    b_execution_count = 0

    Courier = _courier_cls()
    home = tmp_path / "home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()

    courier = Courier(home, logs)
    try:
        # 1. Boot Controller
        courier.start_controller(timeout=20)

        # 2. Setup Ledger and Missions: A is ready, B depends on A
        ledger_file = home / "coordination_ledger.jsonl"
        store = FileCoordinationStore(ledger_file)
        store.write_event(_event("a-assigned", "A", "2026-10-11T12:00:00Z"))
        store.write_event(_event("b-assigned", "B", "2026-10-11T12:00:01Z", deps=["A"]))

        # Spec configs
        unit_a = "artifact-payload-A"
        unit_b = "artifact-payload-B"
        (home / "ledger_tasks.json").write_text(
            json.dumps({"A": _spec(unit_a), "B": _spec(unit_b)}),
            encoding="utf-8",
        )

        # Verify initial state: B is NOT resumable because A is not DONE
        init_reducer = reduce_store(store)
        resumable_init = [c.mission_id for c in discover_resumable(init_reducer, AgentID.GOOGLE_WINDOWS)]
        assert "A" in resumable_init
        assert "B" not in resumable_init, "B must NOT be resumable before A is done"

        # 3. First Bridge Pass: Dispatch A
        bridge1 = _run_bridge(home, courier.base_url)
        assert bridge1.returncode == 0, f"Bridge 1 failed: {bridge1.stderr}"
        
        # Verify Task A was posted to Controller
        tasks_created = [e for e in courier.all_events() if e["type"] == "TASK_CREATED"]
        assert len(tasks_created) == 1
        task_a_id = tasks_created[0]["task_id"]

        state_after_1 = json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))
        assert state_after_1["missions"]["A"]["posted"] is True
        assert "B" not in state_after_1["missions"]  # B was NOT posted

        # 4. Start Worker for Task A
        worker = courier.start_worker()
        view_a = _wait_complete(courier, task_a_id)
        courier.stop_worker_graceful(worker, timeout=15)
        a_execution_count += 1

        # Check verifier accepted A
        events_a = courier.task_events(task_a_id)
        assert "RESULT_ACCEPTED" in [e["type"] for e in events_a]
        accepted_result_id_a = view_a["accepted_result_id"]
        assert accepted_result_id_a is not None

        # Check artifact written by synthetic adapter
        expected_sha_a = hashlib.sha256(unit_a.encode("utf-8")).hexdigest()
        assert view_a["status"] == "COMPLETE"
        assert view_a["attempt"] == 1

        # 5. Bridge Pass: Feedback A -> Ledger Reconciled -> B automatically discovers & dispatches
        # NOTE: No human input or relay message!
        bridge2 = _run_bridge(home, courier.base_url)
        assert bridge2.returncode == 0, f"Bridge 2 failed: {bridge2.stderr}"

        # Ledger now has FINAL event for A
        reducer_after_a = reduce_store(store)
        finals = [e for e in reducer_after_a.events if e.event_type == EventType.FINAL]
        assert len(finals) == 1
        assert finals[0].mission_id == "A"
        assert f"task_id={task_a_id}" in finals[0].evidence_ref
        assert f"accepted_result_id={accepted_result_id_a}" in finals[0].evidence_ref

        # Check that B is now READY and was automatically queued in Controller
        tasks_created_2 = [e for e in courier.all_events() if e["type"] == "TASK_CREATED"]
        assert len(tasks_created_2) == 2, "Task B must be automatically created upon A completion"
        task_b_id = next(e["task_id"] for e in tasks_created_2 if e["task_id"] != task_a_id)

        state_after_2 = json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))
        assert state_after_2["missions"]["B"]["task_id"] == task_b_id
        assert state_after_2["missions"]["B"]["posted"] is True

        # 6. Execute B
        worker_b = courier.start_worker()
        view_b = _wait_complete(courier, task_b_id)
        courier.stop_worker_graceful(worker_b, timeout=15)
        b_execution_count += 1

        events_b = courier.task_events(task_b_id)
        assert "RESULT_ACCEPTED" in [e["type"] for e in events_b]
        accepted_result_id_b = view_b["accepted_result_id"]
        assert accepted_result_id_b is not None

        # 7. Bridge Pass: Feedback B -> Ledger Reconciled B
        bridge3 = _run_bridge(home, courier.base_url)
        assert bridge3.returncode == 0, f"Bridge 3 failed: {bridge3.stderr}"

        reducer_after_b = reduce_store(store)
        finals_all = [e for e in reducer_after_b.events if e.event_type == EventType.FINAL]
        assert len(finals_all) == 2
        mission_finals = {e.mission_id: e for e in finals_all}
        assert "A" in mission_finals
        assert "B" in mission_finals
        assert f"task_id={task_b_id}" in mission_finals["B"].evidence_ref
        assert f"accepted_result_id={accepted_result_id_b}" in mission_finals["B"].evidence_ref

        end_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        duration_s = round(time.time() - start_time, 2)

        # Print metrics report for audit verification
        metrics = {
            "HUMAN_RELAY_COUNT": human_relay_count,
            "A_EXECUTION_COUNT": a_execution_count,
            "B_EXECUTION_COUNT": b_execution_count,
            "START_TIME": start_iso,
            "END_TIME": end_iso,
            "DURATION_SECONDS": duration_s,
            "TASK_A": {
                "task_id": task_a_id,
                "result_id": accepted_result_id_a,
                "artifact_sha256": expected_sha_a,
                "status": "COMPLETE",
            },
            "TASK_B": {
                "task_id": task_b_id,
                "result_id": accepted_result_id_b,
                "artifact_sha256": hashlib.sha256(unit_b.encode("utf-8")).hexdigest(),
                "status": "COMPLETE",
            },
            "LEDGER_FINAL_EVENTS": len(finals_all),
        }
        print("\n=== METRICS REPORT ===")
        print(json.dumps(metrics, indent=2))

        assert human_relay_count == 0
        assert a_execution_count == 1
        assert b_execution_count == 1

    finally:
        courier.close()
