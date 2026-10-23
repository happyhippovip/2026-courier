"""B receives A's verified output, on the real V1 controller and synthetic worker.

The bridge posts B only after it has read A's verifier-accepted result from
GET /v1/tasks/<id>/result and re-hashed every artifact on disk. The synthetic
adapter is the contract proof. It is not a provider, and this does not prove a
production A->B run.
"""

import hashlib
import importlib.util
import json
import os
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
    spec = importlib.util.spec_from_file_location("ledger_inputs_golden_harness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Courier


def _event(eid, mid, ts, deps=None):
    return CoordinationEvent(
        event_id=eid, mission_id=mid, agent_id=AgentID.GOOGLE_WINDOWS, host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED, status=MissionStatus.WORKING, depends_on=deps or [],
        head="sha", evidence_ref="ref", created_at=ts, payload_hash="h", ownership=AGENT,
    )


def _spec(unit, inputs_from=None):
    spec = {
        "adapter": "synthetic",
        "params": {"sleep_s": 0, "write": "out.txt", "content": unit, "hang": False,
                   "fail_transient_n": 0, "fault_attempts": [1]},
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
        "estimated_cost_eur": 0.0,
    }
    if inputs_from is not None:
        spec["inputs_from"] = inputs_from
    return spec


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
    raise AssertionError(f"task {task_id} not COMPLETE; last={last!r}")


def _created(courier):
    return [event for event in courier.all_events() if event["type"] == "TASK_CREATED"]


def _finals(home):
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    return [event for event in reducer.events if event.event_type == EventType.FINAL]


def _setup(tmp_path, b_deps, b_inputs):
    Courier = _courier_cls()
    home = tmp_path / "home"
    logs = tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    courier = Courier(home, logs)
    courier.start_controller(timeout=20)
    store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    store.write_event(_event("a-assign", "A", "2026-10-08T04:00:00Z"))
    store.write_event(_event("b-assign", "B", "2026-10-08T04:00:01Z", deps=b_deps))
    specs = {"A": _spec("unit-a"), "B": _spec("unit-b", b_inputs)}
    (home / "ledger_tasks.json").write_text(json.dumps(specs), encoding="utf-8")
    return courier, home


def _run_a(courier, home):
    first = _bridge(home, courier.base_url)
    assert first.returncode == 0, first.stderr + first.stdout
    created = _created(courier)
    assert len(created) == 1
    task_a = created[0]["task_id"]
    worker = courier.start_worker()
    view_a = _wait_complete(courier, task_a)
    courier.stop_worker_graceful(worker, timeout=15)
    return task_a, view_a


def test_b_receives_a_verified_artifact(tmp_path):
    courier, home = _setup(tmp_path, ["A"], ["A"])
    try:
        unknown = courier.api.get("/v1/tasks/task-unknown/result", timeout=5)
        assert unknown.status_code == 404
        task_a, view_a = _run_a(courier, home)

        result = courier.api.get(f"/v1/tasks/{task_a}/result", timeout=5)
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["task_id"] == task_a
        assert body["result_id"] == view_a["accepted_result_id"]
        assert len(body["artifacts"]) == 1
        artifact = body["artifacts"][0]
        on_disk = hashlib.sha256((home / artifact["path"]).read_bytes()).hexdigest()
        assert artifact["sha256"] == on_disk

        second = _bridge(home, courier.base_url)
        assert second.returncode == 0, second.stderr + second.stdout
        created = _created(courier)
        assert len(created) == 2
        task_b = next(event["task_id"] for event in created if event["task_id"] != task_a)
        not_yet = courier.api.get(f"/v1/tasks/{task_b}/result", timeout=5)
        assert not_yet.status_code == 409
        posted_b = courier.api.get(f"/v1/tasks/{task_b}", timeout=5).json()
        assert posted_b["params"]["inputs"] == [{
            "mission_id": "A", "task_id": task_a, "result_id": view_a["accepted_result_id"],
            "path": artifact["path"], "sha256": on_disk,
        }]
        state = json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))
        digest = state["missions"]["B"]["inputs_digest"]
        assert digest == bridge._inputs_digest(posted_b["params"]["inputs"])

        # A replay posts nothing new and keeps the same inputs.
        replay = _bridge(home, courier.base_url)
        assert replay.returncode == 0, replay.stderr
        assert len(_created(courier)) == 2

        worker_b = courier.start_worker()
        _wait_complete(courier, task_b)
        courier.stop_worker_graceful(worker_b, timeout=15)
        done = _bridge(home, courier.base_url)
        assert done.returncode == 0, done.stderr
        final_b = next(event for event in _finals(home) if event.mission_id == "B")
        assert f"inputs_digest={digest}" in final_b.evidence_ref
        assert final_b.payload_hash == hashlib.sha256(final_b.evidence_ref.encode("utf-8")).hexdigest()
    finally:
        courier.close()


def test_changed_artifact_bytes_block_b(tmp_path):
    courier, home = _setup(tmp_path, ["A"], ["A"])
    try:
        task_a, _ = _run_a(courier, home)
        artifact = courier.api.get(f"/v1/tasks/{task_a}/result", timeout=5).json()["artifacts"][0]
        (home / artifact["path"]).write_bytes(b"tampered")

        run = _bridge(home, courier.base_url)
        assert run.returncode == bridge.EXIT_CONFIG
        assert "input_digest_mismatch" in run.stdout
        assert len(_created(courier)) == 1
        state = json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))
        assert "B" not in state["missions"]
    finally:
        courier.close()


def test_undeclared_input_is_refused(tmp_path):
    courier, home = _setup(tmp_path, [], ["A"])
    try:
        run = _bridge(home, courier.base_url)
        assert run.returncode == bridge.EXIT_CONFIG
        assert "input_not_declared" in run.stdout
        created = _created(courier)
        assert len(created) == 1
        state = json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))
        assert "B" not in state["missions"]
    finally:
        courier.close()


def test_inputs_from_spec_shape():
    base = _spec("x")
    assert bridge._spec_ok(base)
    assert bridge._spec_ok({**base, "inputs_from": ["A"]})
    assert bridge._spec_ok({**base, "inputs_from": ["A", "C"]})
    for bad in ([], ["A", "A"], [""], [1], "A", ["x" * (bridge.MAX_ID_LENGTH + 1)],
                [f"m{i}" for i in range(bridge.MAX_INPUTS + 1)]):
        assert not bridge._spec_ok({**base, "inputs_from": bad}), bad


def test_artifact_path_must_stay_under_artifacts():
    assert bridge._artifact_path_ok("artifacts/d-1/out.txt")
    for bad in ("out.txt", "artifacts/out.txt", "/artifacts/d/out.txt", "artifacts/../x/y", "artifacts/d/./y",
                "artifacts//y", "artifacts\\d\\y", "", None, "a" * 2000):
        assert not bridge._artifact_path_ok(bad), bad


def test_file_sha256_refuses_escape(tmp_path):
    (tmp_path / "artifacts" / "d").mkdir(parents=True)
    (tmp_path / "artifacts" / "d" / "out.txt").write_bytes(b"ok")
    (tmp_path / "secret.txt").write_bytes(b"no")
    assert bridge._file_sha256(tmp_path, "artifacts/d/out.txt") == hashlib.sha256(b"ok").hexdigest()
    assert bridge._file_sha256(tmp_path, "artifacts/d/missing.txt") is None
    try:
        os.symlink(tmp_path / "secret.txt", tmp_path / "artifacts" / "d" / "link.txt")
    except (OSError, NotImplementedError):
        return
    assert bridge._file_sha256(tmp_path, "artifacts/d/link.txt") is None


class _Args:
    controller = "http://127.0.0.1:1"
    timeout = 1.0


def _fake(result):
    def transport(method, url, headers, body, timeout):
        assert method == "GET" and url.endswith("/result")
        if result is None:
            return 409, b'{"error":"not_verified"}'
        return 200, json.dumps(result).encode("utf-8")
    return transport


def _state(status="FINAL_DONE"):
    return {"missions": {"A": {"task_id": "task-a", "idempotency_key": "k", "status": status,
                               "accepted_result_id": "r-1"}}}


def _artifacts(tmp_path, count):
    out = []
    for i in range(count):
        path = f"artifacts/d/out{i}.txt"
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(str(i).encode())
        out.append({"path": path, "sha256": hashlib.sha256(str(i).encode()).hexdigest()})
    return out


def test_c_receives_only_bs_verified_bytes(tmp_path):
    """C is the next handoff. It waits while B is open and refuses B's bytes when they change."""
    spec = {"inputs_from": ["B"]}
    mission = {"depends_on": ["B"]}
    waiting = {"missions": {"B": {"task_id": "task-b", "status": "POSTED", "accepted_result_id": "r-b"}}}
    assert bridge._resolve_inputs(waiting, spec, mission, _fake(None), _Args, "t", tmp_path) == (
        None, "input_not_final", False,
    )

    path = "artifacts/d/from-b.txt"
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"from-b")
    digest = hashlib.sha256(b"from-b").hexdigest()
    ready = {"missions": {"B": {"task_id": "task-b", "status": "FINAL_DONE", "accepted_result_id": "r-b"}}}
    result = {"task_id": "task-b", "result_id": "r-b", "artifacts": [{"path": path, "sha256": digest}]}
    inputs, why, fatal = bridge._resolve_inputs(ready, spec, mission, _fake(result), _Args, "t", tmp_path)
    assert why is None and fatal is False
    assert inputs == [{
        "mission_id": "B", "task_id": "task-b", "result_id": "r-b", "path": path, "sha256": digest,
    }]

    target.write_bytes(b"tampered")
    assert bridge._resolve_inputs(ready, spec, mission, _fake(result), _Args, "t", tmp_path) == (
        None, "input_digest_mismatch", True,
    )


def test_resolve_inputs_waits_for_upstream(tmp_path):
    spec = {"inputs_from": ["A"]}
    mission = {"depends_on": ["A"]}
    got = bridge._resolve_inputs(_state("POSTED"), spec, mission, _fake(None), _Args, "t", tmp_path)
    assert got == (None, "input_not_final", False)


def test_resolve_inputs_refuses_other_result(tmp_path):
    spec = {"inputs_from": ["A"]}
    mission = {"depends_on": ["A"]}
    result = {"task_id": "task-a", "result_id": "r-other", "artifacts": _artifacts(tmp_path, 1)}
    got = bridge._resolve_inputs(_state(), spec, mission, _fake(result), _Args, "t", tmp_path)
    assert got == (None, "input_unverified", True)
    got = bridge._resolve_inputs(_state(), spec, mission, _fake(None), _Args, "t", tmp_path)
    assert got == (None, "input_unverified", True)


def test_resolve_inputs_caps_artifact_count(tmp_path):
    spec = {"inputs_from": ["A"]}
    mission = {"depends_on": ["A"]}
    ok = {"task_id": "task-a", "result_id": "r-1", "artifacts": _artifacts(tmp_path, bridge.MAX_INPUT_ARTIFACTS)}
    inputs, why, fatal = bridge._resolve_inputs(_state(), spec, mission, _fake(ok), _Args, "t", tmp_path)
    assert why is None and not fatal and len(inputs) == bridge.MAX_INPUT_ARTIFACTS
    big = {"task_id": "task-a", "result_id": "r-1", "artifacts": _artifacts(tmp_path, bridge.MAX_INPUT_ARTIFACTS + 1)}
    got = bridge._resolve_inputs(_state(), spec, mission, _fake(big), _Args, "t", tmp_path)
    assert got == (None, "input_too_large", True)
