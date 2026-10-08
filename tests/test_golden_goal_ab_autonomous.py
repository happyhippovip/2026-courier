"""Goal -> A -> B -> DONE with no bridge call from the test.

One real controller and one worker started with the ledger idle tick
(courier_worker.ledger_tick). The ledger holds a goal with two missions, and
B depends on A. The test only starts processes and observes them; every
bridge pass comes from the worker's own idle tick. After A is COMPLETE, and
before the next pass may run, the worker is killed hard (kill -9 / TerminateProcess)
and restarted once.

The synthetic adapter is the contract proof, not a provider. This shows that
the hand-over between A and B needs no human or driver. It does not show a
production provider run.

Like tests/test_golden_ledger_bridge_ab.py, this file lives outside
tests/golden, so the golden skip does not apply. It has no skip marker.
"""

import hashlib
import importlib.util
import json
import time
from collections import Counter
from pathlib import Path

from courier_core.events import effect_key
from scripts.coordination_ledger import (
    AgentID, CoordinationEvent, EventType, HostID, MissionStatus,
)
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore

REPO = Path(__file__).resolve().parents[1]
AGENT = "GOOGLE_WINDOWS"
HOST = "WINDOWS_REMOTE"
GOAL_ID = "goal.tick.ab"
GOAL_FP = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
# A pass may run at most once per interval. A completes well inside one
# interval, so the hard kill lands after A and before the pass that posts B.
TICK_INTERVAL_S = 12.0
HEARTBEAT_S = 0.5
DONE_TIMEOUT_S = 120.0


def _courier_cls():
    path = REPO / "tests" / "golden" / "golden_harness.py"
    spec = importlib.util.spec_from_file_location("ledger_tick_golden_harness", path)
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
        "params": {"sleep_s": 0, "write": "out.txt", "content": unit, "hang": False,
                   "fail_transient_n": 0, "fault_attempts": [1]},
        "effect_class": "idempotent",
        "max_attempts": 2,
        "lease_ttl_s": 10,
        "goal_id": GOAL_ID,
        "goal_fingerprint": GOAL_FP,
    }


def _start_worker_with_tick(courier):
    worker = courier._spawn(
        ["courier_worker.host", "--home", str(courier.home), "--controller", courier.base_url,
         "--max-tasks", "1", "--heartbeat", str(HEARTBEAT_S),
         "--ledger-agent-id", AGENT, "--ledger-host-id", HOST,
         "--ledger-tick-interval", str(TICK_INTERVAL_S), "--ledger-tick-timeout", "60"],
        f"worker-{len(courier.workers)}.log", new_group=True)
    courier.workers.append(worker)
    return worker


def _created(courier):
    return [e for e in courier.all_events() if e["type"] == "TASK_CREATED"]


def _finals(home):
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    return [e for e in reducer.events if e.event_type == EventType.FINAL]


def _state(home):
    path = home / "ledger_bridge_state.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"missions": {}}


def _tick_status(home):
    path = home / "run" / "ledger_tick.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _diag(courier):
    return "\n".join([
        "controller:", courier.log_tail("controller.log"),
        *[f"worker-{i}:\n" + courier.log_tail(f"worker-{i}.log") for i in range(len(courier.workers))],
        f"tick: {_tick_status(courier.home)!r}",
        f"state: {_state(courier.home)!r}",
    ])


def _wait(courier, predicate, timeout, what, interval=0.1):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        worker = courier.workers[-1] if courier.workers else None
        if worker is not None and worker.poll() is not None:
            raise AssertionError(f"worker exited ({worker.returncode}) while waiting for {what}\n{_diag(courier)}")
        time.sleep(interval)
    raise AssertionError(f"timed out after {timeout}s waiting for {what}\n{_diag(courier)}")


def _status(courier, task_id):
    response = courier.api.get(f"/v1/tasks/{task_id}", timeout=5)
    return response.json() if response.status_code == 200 else None


def test_goal_a_then_b_done_by_worker_tick_across_hard_kill(tmp_path):
    Courier = _courier_cls()
    home = tmp_path / "home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    courier = Courier(home, logs)
    try:
        courier.start_controller(timeout=30)
        store = FileCoordinationStore(home / "coordination_ledger.jsonl")
        store.write_event(_event("a-assign", "A", "2026-10-08T04:00:00Z"))
        store.write_event(_event("b-assign", "B", "2026-10-08T04:00:01Z", deps=["A"]))
        (home / "ledger_tasks.json").write_text(
            json.dumps({"A": _spec("unit-a"), "B": _spec("unit-b")}), encoding="utf-8")
        token = (home / "run" / "controller.token").read_text(encoding="utf-8").strip()

        # 1. The worker's first idle tick posts A. The test calls no bridge.
        _start_worker_with_tick(courier)
        created = _wait(courier, lambda: _created(courier), 60, "A posted by the idle tick")
        assert len(created) == 1
        task_a = created[0]["task_id"]
        assert _state(home)["missions"]["A"]["task_id"] == task_a
        assert "B" not in _state(home)["missions"]

        # 2. A completes. Kill -9 before the next pass can feed it back.
        view_a = _wait(courier, lambda: (_status(courier, task_a) or {}).get("status") == "COMPLETE"
                       and _status(courier, task_a), 60, "A COMPLETE")
        courier.kill_worker()
        assert len(_created(courier)) == 1, "B was posted before the hard kill; widen TICK_INTERVAL_S"
        assert _finals(home) == []

        # 3. One restart. Its first idle tick feeds A back and posts B; a later
        #    tick feeds B back. Still no bridge call from the test.
        _start_worker_with_tick(courier)

        def done():
            finals = _finals(home)
            missions = _state(home)["missions"]
            return ({e.mission_id for e in finals} == {"A", "B"}
                    and all(missions.get(m, {}).get("status") == "FINAL_DONE" for m in ("A", "B")))

        _wait(courier, done, DONE_TIMEOUT_S, "A and B FINAL_DONE")

        # 4. Exactly two tasks, both COMPLETE with one accepted result each.
        created = _created(courier)
        assert len(created) == 2, created
        task_ids = [e["task_id"] for e in created]
        assert len(set(task_ids)) == 2
        task_b = next(t for t in task_ids if t != task_a)
        views = {t: _status(courier, t) for t in task_ids}
        assert all(v["status"] == "COMPLETE" and v["accepted_result_id"] for v in views.values()), views
        assert views[task_a]["accepted_result_id"] == view_a["accepted_result_id"]
        for task_id in task_ids:
            types = Counter(e["type"] for e in courier.task_events(task_id))
            assert types["RESULT_ACCEPTED"] == 1, (task_id, types)
            assert types["TASK_COMPLETE"] == 1, (task_id, types)

        # 5. Unique effect keys and the synthetic artifact of each unit.
        keys = {effect_key(t) for t in task_ids}
        assert len(keys) == 2
        for task_id, unit in ((task_a, "unit-a"), (task_b, "unit-b")):
            ready = [e for e in courier.task_events(task_id) if e["type"] == "RESULT_READY"]
            accepted = [json.loads(e["payload"]) for e in ready]
            digest = hashlib.sha256(unit.encode("utf-8")).hexdigest()
            assert any(a.get("sha256") == digest for p in accepted for a in p.get("artifacts", [])), accepted

        # 6. Ledger: exactly one FINAL per mission, bound to its task and goal.
        finals = _finals(home)
        assert Counter(e.mission_id for e in finals) == Counter({"A": 1, "B": 1})
        state = _state(home)["missions"]
        assert {state["A"]["task_id"], state["B"]["task_id"]} == set(task_ids)
        assert len({state["A"]["idempotency_key"], state["B"]["idempotency_key"]}) == 2
        for event in finals:
            assert f"task_id={state[event.mission_id]['task_id']}" in event.evidence_ref
            assert f"goal_id={GOAL_ID}" in event.evidence_ref
            assert event.payload_hash == hashlib.sha256(event.evidence_ref.encode("utf-8")).hexdigest()

        # 7. Replay is a no-op: let the tick run at least one more pass.
        frozen = (home / "coordination_ledger.jsonl").read_bytes()
        before = _tick_status(home)
        assert before and before["parked_reason"] is None, before
        _wait(courier, lambda: (_tick_status(home) or {}).get("passes", 0) > before["passes"],
              TICK_INTERVAL_S * 3, "one more idle pass")
        after = _tick_status(home)
        assert after["outcome"] == "ran" and after["exit_code"] == 0, after
        assert (home / "coordination_ledger.jsonl").read_bytes() == frozen
        assert len(_created(courier)) == 2

        # 8. No secret in any worker or bridge log.
        for path in [*logs.iterdir(), home / "run" / "ledger_bridge.log", home / "run" / "ledger_tick.json"]:
            if path.exists():
                assert token not in path.read_text(encoding="utf-8", errors="replace"), path
        courier.stop_worker_graceful(timeout=20)
    finally:
        courier.close()
