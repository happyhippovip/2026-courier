"""Deterministic 5-Task Sequential Workkey Progression (A -> B -> C -> D -> E).

Mission: Nach jedem echten Abschluss muss Courier einen anderen Workkey wählen.

Akzeptanzkriterien:
- Kein Workkey wird doppelt ausgeführt.
- Ein abgeschlossener Workkey wird nicht wieder READY.
- BLOCKED wird nicht stillschweigend übergangen.
- Die Reihenfolge respektiert Dependencies (A -> B -> C -> D -> E, mit C geblockt für ein isoliertes Kriterium oder einer sauberen Kette).
- Die fünfte Aufgabe endet mit einem begründeten TRUE_IDLE.
- Echte Prozess- und Worker-Ausführungen mit Controller, Worker und Ledger-Bridge.
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

from scripts.coordination_delivery import NextActionType
from scripts.coordination_engine import CoordinationEngine
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
GOAL_ID = "goal.chain.five"
GOAL_FP = "99887766554433221100aabbccddeeff99887766554433221100aabbccddeeff"


def _courier_cls():
    path = REPO / "tests" / "golden" / "golden_harness.py"
    spec = importlib.util.spec_from_file_location("chain_golden_harness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Courier


def _event(eid, mid, ts, deps=None, status=MissionStatus.WORKING):
    return CoordinationEvent(
        event_id=eid,
        mission_id=mid,
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED,
        status=status,
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


def test_one_finished_task_means_next_different_task_chain(tmp_path):
    """Execute a 5-task DAG: A -> B -> C -> D -> E.

    Verify:
    1. Every step selects the NEXT DIFFERENT task.
    2. Executed tasks never return to READY / resumable.
    3. No task is executed twice.
    4. Execution order strictly adheres to dependencies.
    5. When BLOCKED is encountered on a branch, it is NOT silently skipped.
    6. When all tasks complete, the resolver signals TRUE_IDLE.
    """
    Courier = _courier_cls()
    home = tmp_path / "home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()

    courier = Courier(home, logs)
    try:
        courier.start_controller(timeout=20)
        store = FileCoordinationStore(home / "coordination_ledger.jsonl")

        # 5 missions in DAG:
        # A (no deps)
        # B (deps: [A])
        # C (deps: [B])
        # D (deps: [C])
        # E (deps: [D])
        store.write_event(_event("a-assign", "A", "2026-10-11T14:00:00Z"))
        store.write_event(_event("b-assign", "B", "2026-10-11T14:00:01Z", deps=["A"]))
        store.write_event(_event("c-assign", "C", "2026-10-11T14:00:02Z", deps=["B"]))
        store.write_event(_event("d-assign", "D", "2026-10-11T14:00:03Z", deps=["C"]))
        store.write_event(_event("e-assign", "E", "2026-10-11T14:00:04Z", deps=["D"]))

        tasks_spec = {
            "A": _spec("unit-A"),
            "B": _spec("unit-B"),
            "C": _spec("unit-C"),
            "D": _spec("unit-D"),
            "E": _spec("unit-E"),
        }
        (home / "ledger_tasks.json").write_text(json.dumps(tasks_spec), encoding="utf-8")

        executed_order = []
        task_id_map = {}

        # Loop through each step in the DAG
        for expected_mission in ["A", "B", "C", "D", "E"]:
            # Check DAG selection before bridge dispatch
            reducer = reduce_store(store)
            resumable = discover_resumable(reducer, AgentID.GOOGLE_WINDOWS)
            resumable_ids = [c.mission_id for c in resumable]

            # Invariant: Completed tasks MUST NOT be resumable / READY
            for prev in executed_order:
                assert prev not in resumable_ids, f"Completed task {prev} became READY again!"

            # Exactly the next dependent task must be selected
            assert expected_mission in resumable_ids, f"Expected {expected_mission} to be READY"
            assert resumable_ids[0] == expected_mission, f"Wrong selection: expected {expected_mission}, got {resumable_ids}"

            # Run bridge to post task
            proc = _bridge(home, courier.base_url)
            assert proc.returncode == 0, proc.stderr

            state = json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))
            task_id = state["missions"][expected_mission]["task_id"]
            task_id_map[expected_mission] = task_id

            # Execute via worker
            worker = courier.start_worker()
            view = _wait_complete(courier, task_id)
            courier.stop_worker_graceful(worker, timeout=15)
            assert view["status"] == "COMPLETE"
            assert view["accepted_result_id"]

            executed_order.append(expected_mission)

            # Bridge reconciles completion into ledger
            proc_reconcile = _bridge(home, courier.base_url)
            assert proc_reconcile.returncode == 0, proc_reconcile.stderr

            # Verify ledger records FINAL
            reducer_after = reduce_store(store)
            mission_record = reducer_after.get_mission(expected_mission)
            assert mission_record["status"] == MissionStatus.DONE

        # Verification after all 5 tasks complete:
        assert executed_order == ["A", "B", "C", "D", "E"]
        assert len(set(executed_order)) == 5, "Duplicate workkey execution detected!"

        # Check TRUE_IDLE termination
        final_reducer = reduce_store(store)
        resumable_final = discover_resumable(final_reducer, AgentID.GOOGLE_WINDOWS)
        assert len(resumable_final) == 0, "No workkeys should remain resumable"

        engine = CoordinationEngine(final_reducer)
        dag_actions = engine.evaluate_dag()
        assert len(dag_actions) == 1
        assert dag_actions[0].action_type == NextActionType.TRUE_IDLE
        assert "All 5 DAG missions are DONE" in dag_actions[0].reason

        # Re-running bridge when all work is DONE must not dispatch anything (idle exit 0)
        idle_bridge = _bridge(home, courier.base_url)
        assert idle_bridge.returncode == 0
        assert "queued" not in idle_bridge.stdout

    finally:
        courier.close()


def test_blocked_task_is_not_silently_skipped_and_blocks_dependents(tmp_path):
    """BLOCKED task on dependent branch is never silently skipped or bypassed."""
    store_file = tmp_path / "coordination_ledger.jsonl"
    store = FileCoordinationStore(store_file)

    # A is DONE
    store.write_event(CoordinationEvent(
        event_id="e1", mission_id="A", agent_id=AgentID.GOOGLE_WINDOWS, host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.FINAL, status=MissionStatus.DONE, depends_on=[],
        head="sha", evidence_ref="ref", created_at="2026-10-11T14:00:00Z", payload_hash="h"
    ))
    # B is BLOCKED (requires human action / approval)
    store.write_event(CoordinationEvent(
        event_id="e2", mission_id="B", agent_id=AgentID.GOOGLE_WINDOWS, host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.BLOCKED, status=MissionStatus.BLOCKED, depends_on=["A"],
        head="sha", evidence_ref="ref", created_at="2026-10-11T14:00:01Z", payload_hash="h",
        blocker="Human gate: waiting for secret approval"
    ))
    # C depends on B
    store.write_event(CoordinationEvent(
        event_id="e3", mission_id="C", agent_id=AgentID.GOOGLE_WINDOWS, host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED, status=MissionStatus.WORKING, depends_on=["B"],
        head="sha", evidence_ref="ref", created_at="2026-10-11T14:00:02Z", payload_hash="h"
    ))

    reducer = reduce_store(store)
    # 1. B is BLOCKED, not offered by discover_resumable
    resumable = discover_resumable(reducer, AgentID.GOOGLE_WINDOWS)
    assert "B" not in [c.mission_id for c in resumable]
    # 2. C depends on B (which is not DONE), so C is NOT offered either
    assert "C" not in [c.mission_id for c in resumable]

    # 3. DAG evaluator explicitly flags B as HUMAN_ACTION_REQUIRED, not ignored!
    engine = CoordinationEngine(reducer)
    actions = engine.evaluate_dag()
    assert any(a.mission_id == "B" and a.action_type == NextActionType.HUMAN_ACTION_REQUIRED for a in actions)
    assert any(a.mission_id == "C" and a.action_type == NextActionType.HUMAN_ACTION_REQUIRED for a in actions)
    assert engine.select_first_ready() is None
