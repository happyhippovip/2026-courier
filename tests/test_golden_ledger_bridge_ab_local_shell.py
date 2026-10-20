"""A then B on the real V1 controller, worker, verifier and ledger bridge,
with a real local process instead of the synthetic adapter.

local_shell runs an argv command in the task sandbox; the verifier checks the
evidence file it wrote. No provider, no network, no cost. This proves the
controller/worker chain with a non-synthetic execution; it does not prove a
model provider run.
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
GOAL_ID = "goal.bridge.ab.local"
GOAL_FP = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"


def _courier_cls():
    path = REPO / "tests" / "golden" / "golden_harness.py"
    spec = importlib.util.spec_from_file_location("ledger_bridge_local_shell_harness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Courier


def _event(eid, mid, ts, deps=None):
    return CoordinationEvent(
        event_id=eid, mission_id=mid, agent_id=AgentID.GOOGLE_WINDOWS, host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED, status=MissionStatus.WORKING, depends_on=deps or [],
        head="sha", evidence_ref="ref", created_at=ts, payload_hash="h", ownership=AGENT,
    )


def _spec(code):
    return {
        "adapter": "local_shell",
        "params": {"command": [sys.executable, "-c", code], "write": "out.txt", "timeout_s": 30},
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
        "goal_id": GOAL_ID,
        "goal_fingerprint": GOAL_FP,
    }


WRITE_A = "import pathlib; pathlib.Path('out.txt').write_text('unit-a')"
WRITE_B = "import pathlib; pathlib.Path('out.txt').write_text('unit-b')"
FAIL = "import sys; sys.exit(3)"


def _bridge(home, url):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "scripts.ledger_v1_bridge",
         "--home", str(home), "--agent-id", AGENT, "--host-id", HOST, "--controller", url],
        cwd=str(REPO), env=env, capture_output=True, text=True, timeout=20, check=False,
    )


def _wait_terminal(courier, task_id, timeout=30):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        response = courier.api.get(f"/v1/tasks/{task_id}", timeout=5)
        if response.status_code == 200:
            last = response.json()
            if last.get("status") in ("COMPLETE", "FAILED", "CANCELLED", "BLOCKED"):
                return last
        time.sleep(0.2)
    raise AssertionError(f"task {task_id} not terminal; last={last!r}\n"
                         f"{courier.log_tail('controller.log')}\n{courier.log_tail('worker-0.log')}")


def _created(courier):
    return [event for event in courier.all_events() if event["type"] == "TASK_CREATED"]


def _finals(home):
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    return [event for event in reducer.events if event.event_type == EventType.FINAL]


def _start(tmp_path, specs, events):
    Courier = _courier_cls()
    home = tmp_path / "home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    courier = Courier(home, logs)
    courier.start_controller(timeout=20)
    store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    for event in events:
        store.write_event(event)
    (home / "ledger_tasks.json").write_text(json.dumps(specs), encoding="utf-8")
    return courier, home


def test_real_local_process_a_then_b_reaches_final(tmp_path):
    courier, home = _start(tmp_path, {"A": _spec(WRITE_A), "B": _spec(WRITE_B)}, [
        _event("a-assign", "A", "2026-10-18T04:00:00Z"),
        _event("b-assign", "B", "2026-10-18T04:00:01Z", deps=["A"]),
    ])
    try:
        assert _bridge(home, courier.base_url).returncode == 0
        task_a = _created(courier)[0]["task_id"]
        worker = courier.start_worker()
        view_a = _wait_terminal(courier, task_a)
        courier.stop_worker_graceful(worker, timeout=15)
        assert view_a["status"] == "COMPLETE", view_a
        assert view_a["accepted_result_id"]
        assert view_a["adapter"] == "local_shell"

        assert _bridge(home, courier.base_url).returncode == 0
        assert [f.mission_id for f in _finals(home)] == ["A"]
        task_b = next(e["task_id"] for e in _created(courier) if e["task_id"] != task_a)

        worker_b = courier.start_worker()
        view_b = _wait_terminal(courier, task_b)
        courier.stop_worker_graceful(worker_b, timeout=15)
        assert view_b["status"] == "COMPLETE", view_b

        assert _bridge(home, courier.base_url).returncode == 0
        assert {f.mission_id for f in _finals(home)} == {"A", "B"}
        for final, view in (("A", view_a), ("B", view_b)):
            event = next(f for f in _finals(home) if f.mission_id == final)
            assert f"accepted_result_id={view['accepted_result_id']}" in event.evidence_ref
    finally:
        courier.close()


def test_failing_local_process_never_becomes_final(tmp_path):
    courier, home = _start(tmp_path, {"A": _spec(FAIL), "B": _spec(WRITE_B)}, [
        _event("a-assign", "A", "2026-10-18T04:00:00Z"),
        _event("b-assign", "B", "2026-10-18T04:00:01Z", deps=["A"]),
    ])
    try:
        assert _bridge(home, courier.base_url).returncode == 0
        task_a = _created(courier)[0]["task_id"]
        worker = courier.start_worker()
        view_a = _wait_terminal(courier, task_a)
        courier.stop_worker_graceful(worker, timeout=15)
        assert view_a["status"] != "COMPLETE", view_a
        assert not view_a.get("accepted_result_id")

        _bridge(home, courier.base_url)
        assert _finals(home) == []
        assert len(_created(courier)) == 1  # B is never posted behind a failed A
    finally:
        courier.close()
