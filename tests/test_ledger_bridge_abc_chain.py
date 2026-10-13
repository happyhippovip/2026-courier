"""A -> B -> C from the coordination ledger, on the real V1 controller and worker.

The ledger says B depends on A and C on B. With bind_input the bridge posts
each dependent task with depends_on = its dependency's controller task; the
controller binds the dependency's verified result as the input at claim, the
runner re-hashes it, the synthetic adapter transforms it and the verifier
recomputes it. C's bytes are the reverse of B's, which are the reverse of A's.

The synthetic adapter is the contract proof. It is not a provider, and this
does not prove a production run.
"""

import hashlib
import importlib.util
import json
import os
import secrets
import string
import subprocess
import sys
import time
from pathlib import Path

from scripts import ledger_v1_bridge as bridge
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
    spec = importlib.util.spec_from_file_location("ledger_abc_golden_harness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Courier


def _event(eid, mid, ts, deps=None):
    return CoordinationEvent(
        event_id=eid, mission_id=mid, agent_id=AgentID.GOOGLE_WINDOWS, host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED, status=MissionStatus.WORKING, depends_on=deps or [],
        head="sha", evidence_ref="ref", created_at=ts, payload_hash="h", ownership=AGENT,
    )


def _spec(**params):
    spec = {
        "adapter": "synthetic",
        "params": {"sleep_s": 0, "write": "out.txt", "hang": False, "fail_transient_n": 0,
                   "fault_attempts": [1], **params},
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
    }
    if "from_input" in params:
        spec["bind_input"] = True
    return spec


def _bridge(home, url):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "scripts.ledger_v1_bridge",
         "--home", str(home), "--agent-id", AGENT, "--host-id", HOST, "--controller", url],
        cwd=str(REPO), env=env, capture_output=True, text=True, timeout=20, check=False,
    )


def _wait_complete(courier, task_id, timeout=30):
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
    raise AssertionError(f"task {task_id} not COMPLETE; last={last!r}\n{courier.log_tail('controller.log')}\n"
                         f"{courier.log_tail('worker-0.log')}")


def _state(home):
    return json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))


def _created(courier):
    return [event for event in courier.all_events() if event["type"] == "TASK_CREATED"]


def _finals(home):
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    return {event.mission_id: event for event in reducer.events if event.event_type == EventType.FINAL}


def _run_next(courier, home, mission_id):
    """One bridge pass posts mission_id; one worker runs it to COMPLETE."""
    run = _bridge(home, courier.base_url)
    assert run.returncode == 0, run.stderr + run.stdout
    task_id = _state(home)["missions"][mission_id]["task_id"]
    worker = courier.start_worker()
    view = _wait_complete(courier, task_id)
    courier.stop_worker_graceful(worker, timeout=15)
    return task_id, view


def _payload(row):
    payload = row["payload"]
    return json.loads(payload) if isinstance(payload, str) else payload


def _artifact_bytes(courier, home, task_id):
    ready = [e for e in courier.all_events() if e["type"] == "RESULT_READY" and e["task_id"] == task_id]
    assert len(ready) == 1
    artifacts = _payload(ready[0])["artifacts"]
    assert len(artifacts) == 1
    data = (home / artifacts[0]["path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == artifacts[0]["sha256"]
    return data


def test_ledger_a_b_c_chain_hands_each_verified_result_on(tmp_path):
    token = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))
    Courier = _courier_cls()
    home = tmp_path / "home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    courier = Courier(home, logs)
    try:
        courier.start_controller(timeout=20)
        store = FileCoordinationStore(home / "coordination_ledger.jsonl")
        store.write_event(_event("a-assign", "A", "2026-10-08T04:00:00Z"))
        store.write_event(_event("b-assign", "B", "2026-10-08T04:00:01Z", deps=["A"]))
        store.write_event(_event("c-assign", "C", "2026-10-08T04:00:02Z", deps=["B"]))
        specs = {"A": _spec(content=token), "B": _spec(from_input="reverse"), "C": _spec(from_input="reverse")}
        (home / "ledger_tasks.json").write_text(json.dumps(specs), encoding="utf-8")

        task_a, _ = _run_next(courier, home, "A")
        assert set(_state(home)["missions"]) == {"A"}
        task_b, _ = _run_next(courier, home, "B")
        task_c, _ = _run_next(courier, home, "C")
        done = _bridge(home, courier.base_url)
        assert done.returncode == 0, done.stderr + done.stdout

        assert _artifact_bytes(courier, home, task_a) == token.encode()
        assert _artifact_bytes(courier, home, task_b) == token[::-1].encode()
        assert _artifact_bytes(courier, home, task_c) == token.encode()

        created = {e["task_id"]: _payload(e) for e in _created(courier)}
        assert "depends_on" not in created[task_a]
        assert created[task_b]["depends_on"] == task_a
        assert created[task_c]["depends_on"] == task_b
        claims = {e["task_id"]: _payload(e) for e in courier.all_events() if e["type"] == "TASK_CLAIMED"}
        assert claims[task_b]["input"]["task_id"] == task_a
        assert claims[task_c]["input"]["task_id"] == task_b
        assert len(claims) == 3

        finals = _finals(home)
        assert set(finals) == {"A", "B", "C"}
        assert "depends_on_task" not in finals["A"].evidence_ref
        assert f"depends_on_task={task_a}" in finals["B"].evidence_ref
        assert f"depends_on_task={task_b}" in finals["C"].evidence_ref
        for event in finals.values():
            assert event.payload_hash == hashlib.sha256(event.evidence_ref.encode("utf-8")).hexdigest()

        frozen = (home / "coordination_ledger.jsonl").read_text(encoding="utf-8")
        again = _bridge(home, courier.base_url)
        assert again.returncode == 0, again.stderr
        assert (home / "coordination_ledger.jsonl").read_text(encoding="utf-8") == frozen
        assert len(_created(courier)) == 3
    finally:
        courier.close()


def test_bind_input_needs_exactly_one_ledger_dependency(tmp_path):
    Courier = _courier_cls()
    home = tmp_path / "home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    courier = Courier(home, logs)
    try:
        courier.start_controller(timeout=20)
        store = FileCoordinationStore(home / "coordination_ledger.jsonl")
        store.write_event(_event("x-assign", "X", "2026-10-08T04:00:00Z"))
        (home / "ledger_tasks.json").write_text(json.dumps({"X": _spec(from_input="copy")}), encoding="utf-8")
        run = _bridge(home, courier.base_url)
        assert run.returncode == bridge.EXIT_CONFIG
        assert "bind_input_needs_one_dependency" in run.stdout
        assert _created(courier) == []
        assert not (home / "ledger_bridge_state.json").exists() or "X" not in _state(home)["missions"]
    finally:
        courier.close()


def test_upstream_task_rules():
    posted = {"task_id": "task-a", "idempotency_key": "k", "posted": True}
    state = {"missions": {"A": posted, "Q": {"task_id": "task-q", "idempotency_key": "k", "posted": False}}}
    assert bridge._upstream_task(state, {"depends_on": ["A"]}) == ("task-a", None)
    assert bridge._upstream_task(state, {"depends_on": []}) == (None, "bind_input_needs_one_dependency")
    assert bridge._upstream_task(state, {"depends_on": ["A", "Q"]}) == (None, "bind_input_needs_one_dependency")
    assert bridge._upstream_task(state, {"depends_on": ["Q"]}) == (None, "dependency_unmapped")
    assert bridge._upstream_task(state, {"depends_on": ["Z"]}) == (None, "dependency_unmapped")
    assert bridge._upstream_task(state, None) == (None, "bind_input_needs_one_dependency")


def test_bind_input_spec_shape():
    base = _spec(content="x")
    assert bridge._spec_ok({**base, "bind_input": True})
    assert bridge._spec_ok({**base, "bind_input": False})
    for bad in ("yes", 1, None, ["A"]):
        assert not bridge._spec_ok({**base, "bind_input": bad}), bad
    # One input mechanism per task: the controller's binding or the bridge's inputs_from.
    assert not bridge._spec_ok({**base, "bind_input": True, "inputs_from": ["A"]})
    assert bridge._spec_ok({**base, "bind_input": False, "inputs_from": ["A"]})


def test_post_task_sends_depends_on_only_when_bound():
    sent = []

    def transport(method, url, headers, body, timeout):
        sent.append(json.loads(body))
        return 201, b'{"task_id":"t"}'

    class Args:
        controller = "http://127.0.0.1:1"
        timeout = 1.0

    spec = _spec(content="x")
    bridge._post_task(transport, Args, "tok", spec, "ledger:k1")
    bridge._post_task(transport, Args, "tok", spec, "ledger:k2", depends_on_task="task-a")
    assert "depends_on" not in sent[0]
    assert sent[1]["depends_on"] == "task-a"
