"""A then B on the real V1 controller and synthetic worker.

The synthetic adapter is the contract proof. It is not a provider, and this
does not prove a production A->B run.

tests/golden is skipped only while its required modules are missing, on every
OS, not on Windows alone. This file lives outside that directory, so that
skip does not apply. It runs wherever the rest of pytest runs.
"""

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from scripts.coordination_ledger import (
    AgentID, CoordinationEvent, EventType, HostID, MissionStatus,
)
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore

REPO = Path(__file__).resolve().parents[1]
AGENT = "GOOGLE_WINDOWS"
HOST = "WINDOWS_REMOTE"


def _courier_cls():
    path = REPO / "tests" / "golden" / "golden_harness.py"
    spec = importlib.util.spec_from_file_location("ledger_bridge_golden_harness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Courier


def _event(eid, mid, ts, deps=None):
    return CoordinationEvent(
        event_id=eid, mission_id=mid, agent_id=AgentID.GOOGLE_WINDOWS, host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED, status=MissionStatus.WORKING, depends_on=deps or [],
        head="sha", evidence_ref="ref", created_at=ts, payload_hash="h", ownership=AGENT,
    )


def _spec(unit):
    return {
        "adapter": "synthetic",
        "params": {
            "sleep_s": 0,
            "write": "out.txt",
            "content": unit,
            "hang": False,
            "fail_transient_n": 0,
            "fault_attempts": [1],
        },
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
    }


def _bridge(home, url):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "scripts.ledger_v1_bridge",
         "--home", str(home), "--agent-id", AGENT, "--host-id", HOST, "--controller", url],
        cwd=str(REPO), env=env, capture_output=True, text=True, timeout=20, check=False,
    )


def _wait_complete(courier, task_id, timeout=20):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        response = courier.api.get(f"/v1/tasks/{task_id}", timeout=5)
        if response.status_code == 200:
            last = response.json()
            if last.get("status") == "COMPLETE":
                return last
            if last.get("status") in ("FAILED", "CANCELLED", "BLOCKED"):
                raise AssertionError(last)
        time.sleep(0.2)
    raise AssertionError(f"task {task_id} not COMPLETE; last={last!r}\n{courier.log_tail('controller.log')}\n{courier.log_tail('worker-0.log')}")


def _created(courier):
    return [event for event in courier.all_events() if event["type"] == "TASK_CREATED"]


def _finals(home):
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    return [event for event in reducer.events if event.event_type == EventType.FINAL]


def _assert_identity(event, view, source_sha):
    evidence = event.evidence_ref
    assert f"task_id={view['task_id']}" in evidence
    assert f"accepted_result_id={view['accepted_result_id']}" in evidence
    assert f"attempt={view['attempt']}" in evidence
    assert f"source_sha={source_sha}" in evidence
    assert "spec_fingerprint=" in evidence
    assert event.event_type == EventType.FINAL


def test_real_controller_ab_and_restart_before_feedback(tmp_path):
    Courier = _courier_cls()
    home = tmp_path / "home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    courier = Courier(home, logs)
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    try:
        courier.start_controller(timeout=20)
        store = FileCoordinationStore(home / "coordination_ledger.jsonl")
        store.write_event(_event("a-assign", "A", "2026-10-08T04:00:00Z"))
        store.write_event(_event("b-assign", "B", "2026-10-08T04:00:01Z", deps=["A"]))
        (home / "ledger_tasks.json").write_text(json.dumps({"A": _spec("unit-a"), "B": _spec("unit-b")}), encoding="utf-8")
        token = (home / "run" / "controller.token").read_text(encoding="utf-8")

        first = _bridge(home, courier.base_url)
        assert first.returncode == 0, first.stderr
        assert token not in first.stdout + first.stderr
        created = _created(courier)
        assert len(created) == 1
        task_a = created[0]["task_id"]
        state = json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))
        assert state["missions"]["A"]["task_id"] == task_a
        assert state["missions"]["A"]["idempotency_key"].startswith("ledger:claim-")
        assert "B" not in state["missions"]

        worker = courier.start_worker()
        view_a = _wait_complete(courier, task_a)
        courier.stop_worker_graceful(worker, timeout=15)
        assert view_a["accepted_result_id"]
        assert view_a["attempt"] == 1

        # The bridge process has exited. This invocation is a fresh process
        # reading the state file after A is already COMPLETE.
        feedback = _bridge(home, courier.base_url)
        assert feedback.returncode == 0, feedback.stderr + feedback.stdout
        assert token not in feedback.stdout + feedback.stderr
        finals = _finals(home)
        assert len(finals) == 1 and finals[0].mission_id == "A"
        _assert_identity(finals[0], view_a, source)
        created = _created(courier)
        assert len(created) == 2
        task_b = next(event["task_id"] for event in created if event["task_id"] != task_a)
        keys = {json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))["missions"][mid]["idempotency_key"]
                for mid in ("A", "B")}
        assert len(keys) == 2
        assert all(key.startswith("ledger:claim-") for key in keys)

        replay = _bridge(home, courier.base_url)
        assert replay.returncode == 0, replay.stderr
        ledger_after_a = (home / "coordination_ledger.jsonl").read_text(encoding="utf-8")
        assert _bridge(home, courier.base_url).returncode == 0
        assert (home / "coordination_ledger.jsonl").read_text(encoding="utf-8") == ledger_after_a
        assert len(_created(courier)) == 2
        assert len(_finals(home)) == 1

        worker_b = courier.start_worker()
        view_b = _wait_complete(courier, task_b)
        courier.stop_worker_graceful(worker_b, timeout=15)
        done = _bridge(home, courier.base_url)
        assert done.returncode == 0, done.stderr
        finals = _finals(home)
        assert {event.mission_id for event in finals} == {"A", "B"}
        final_b = next(event for event in finals if event.mission_id == "B")
        _assert_identity(final_b, view_b, source)
        assert len(_created(courier)) == 2
        frozen = (home / "coordination_ledger.jsonl").read_text(encoding="utf-8")
        again = _bridge(home, courier.base_url)
        assert again.returncode == 0, again.stderr
        assert (home / "coordination_ledger.jsonl").read_text(encoding="utf-8") == frozen
        assert len(_created(courier)) == 2
        assert "queued" not in again.stdout
    finally:
        courier.close()
