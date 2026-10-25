"""A dependent task end to end: the verified result of A reaches B through controller, worker host,
runner, adapter and verifier (L2 + L3 + L4), plus the unit rules of each hop.

No model and no network beyond 127.0.0.1: the adapter is the synthetic one. A pass here is a
product-path pass with a stand-in adapter, not proof of a real provider run.
"""

import hashlib
import json
import secrets
import string
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "controller"))

from ctrl_helpers import LiveService  # noqa: E402

from adapters import synthetic  # noqa: E402
from courier_core.events import EventType  # noqa: E402
from courier_core.state_machine import TaskStatus  # noqa: E402
from courier_core.verification import adapter_verifier  # noqa: E402
from courier_worker import adapter_bridge, adapter_runner  # noqa: E402
from courier_worker import service as worker_service  # noqa: E402
from courier_worker.host import SpecError  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synthetic_task(**params):
    params.setdefault("estimated_cost_eur", 0.0)
    return {"adapter": "synthetic", "params": params, "effect_class": "idempotent", "max_attempts": 1,
            "lease_ttl_s": 30, "timeout_s": 60}


def wait_for(predicate, timeout_s=30.0):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
        except (sqlite3.OperationalError, sqlite3.InterfaceError):
            pass
        time.sleep(0.1)
    return False


def task_state(ctl, task_id):
    with ctl._locked():
        return ctl.journal.task(task_id) if ctl.journal else None


def task_events(ctl, task_id):
    with ctl._locked():
        return list(ctl.journal.events(task_id=task_id)) if ctl.journal else []


def deliver_one(loop, timeout_s=60.0):
    """Run worker cycles until one dispatch was delivered (the host may pause under load)."""
    stop = threading.Event()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if loop.iterate(stop) == "delivered":
            return True
        time.sleep(0.2)
    return False


@pytest.fixture
def live(tmp_path):
    service = LiveService(tmp_path / "home", verifier=adapter_verifier)
    yield service
    service.stop()


# ------------------------------------------------------------------ end to end
def test_real_controller_and_worker_run_a_then_b_on_the_verified_result(live, tmp_path):
    home = tmp_path / "home"
    ctl = live.controller
    token = "".join(secrets.choice(string.ascii_uppercase) for _ in range(8))  # not known before the run
    a = ctl.create_task(synthetic_task(write="token.txt", content=token))[1]["task_id"]
    b = ctl.create_task({**synthetic_task(write="reversed.txt", from_input="reverse"), "depends_on": a})[1]["task_id"]
    loop = worker_service.WorkerLoop(str(home), live.base, "w1", 0.2)

    assert deliver_one(loop)
    assert wait_for(lambda: getattr(task_state(ctl, a), "status", None) is TaskStatus.COMPLETE)
    assert getattr(task_state(ctl, b), "status", None) is TaskStatus.QUEUED

    assert deliver_one(loop)
    assert wait_for(lambda: getattr(task_state(ctl, b), "status", None) is TaskStatus.COMPLETE), getattr(task_state(ctl, b), "last_reason", None)

    state_a, state_b = task_state(ctl, a), task_state(ctl, b)
    bound = state_b.input
    assert bound["task_id"] == a and bound["dispatch_id"] == state_a.dispatch_id
    assert bound["artifacts"] == [{"path": f"artifacts/{state_a.dispatch_id}/token.txt", "sha256": sha(token.encode())}]
    produced = (home / "artifacts" / state_b.dispatch_id / "reversed.txt").read_bytes()
    assert produced == token[::-1].encode()

    events_b = task_events(ctl, b)
    claimed = [e for e in events_b if e.type is EventType.TASK_CLAIMED]
    accepted = [e for e in events_b if e.type is EventType.RESULT_ACCEPTED]
    assert len(claimed) == 1 and claimed[0].payload["input"] == bound
    assert len(accepted) == 1 and accepted[0].payload["verifier"]["name"].startswith("adapters.synthetic")
    assert sum(e.type is EventType.TASK_CLAIMED for e in task_events(ctl, a)) == 1
    assert loop.iterate(threading.Event()) == "idle"  # nothing is dispatched a second time
    with ctl._locked():
        assert ctl.journal.verify_chain().ok and ctl.journal.verify_projection()


def test_a_changed_dependency_artifact_never_reaches_the_adapter(live, tmp_path):
    home = tmp_path / "home"
    ctl = live.controller
    a = ctl.create_task(synthetic_task(write="token.txt", content="ABCD"))[1]["task_id"]
    b = ctl.create_task({**synthetic_task(write="reversed.txt", from_input="reverse"), "depends_on": a})[1]["task_id"]
    loop = worker_service.WorkerLoop(str(home), live.base, "w1", 0.2)
    assert deliver_one(loop)
    assert wait_for(lambda: getattr(task_state(ctl, a), "status", None) is TaskStatus.COMPLETE)
    dispatch_a = task_state(ctl, a).dispatch_id
    (home / "artifacts" / dispatch_a / "token.txt").write_bytes(b"EVIL")  # after verification

    assert deliver_one(loop)
    assert wait_for(lambda: getattr(task_state(ctl, b), "status", None) is TaskStatus.FAILED)
    state_b = task_state(ctl, b)
    assert "input refused" in state_b.last_reason
    assert not (home / "artifacts" / state_b.dispatch_id / "reversed.txt").exists()


def test_controller_restart_between_a_and_b_runs_b_once_and_a_never_again(tmp_path):
    home = tmp_path / "home"
    first = LiveService(home, verifier=adapter_verifier)
    try:
        ctl = first.controller
        a = ctl.create_task(synthetic_task(write="token.txt", content="RESTART"))[1]["task_id"]
        b = ctl.create_task({**synthetic_task(write="reversed.txt", from_input="reverse"), "depends_on": a})[1]["task_id"]
        assert deliver_one(worker_service.WorkerLoop(str(home), first.base, "w1", 0.2))
        assert wait_for(lambda: getattr(task_state(ctl, a), "status", None) is TaskStatus.COMPLETE)
        dispatch_a = task_state(ctl, a).dispatch_id
    finally:
        first.stop()  # the controller process ends before B was ever dispatched

    second = LiveService(home, verifier=adapter_verifier)  # new controller, new port, same journal
    try:
        ctl = second.controller
        assert getattr(task_state(ctl, a), "status", None) is TaskStatus.COMPLETE and getattr(task_state(ctl, b), "status", None) is TaskStatus.QUEUED
        loop = worker_service.WorkerLoop(str(home), second.base, "w2", 0.2)  # a fresh worker as well
        assert deliver_one(loop)
        assert wait_for(lambda: getattr(task_state(ctl, b), "status", None) is TaskStatus.COMPLETE), getattr(task_state(ctl, b), "last_reason", None)
        assert loop.iterate(threading.Event()) == "idle"
        state_b = task_state(ctl, b)
        assert state_b.input["dispatch_id"] == dispatch_a
        assert (home / "artifacts" / state_b.dispatch_id / "reversed.txt").read_bytes() == b"TRATSER"
        for task_id in (a, b):
            kinds = [e.type for e in task_events(ctl, task_id)]
            assert kinds.count(EventType.TASK_CLAIMED) == 1 and kinds.count(EventType.TASK_COMPLETE) == 1
        with ctl._locked():
            assert ctl.journal.verify_chain().ok and ctl.journal.verify_projection()
    finally:
        second.stop()


# ----------------------------------------------------------------- L3: bridge
GOOD_INPUT = {"task_id": "task-a", "dispatch_id": "dsp-a", "result_id": "r-dsp-a",
              "artifacts": [{"path": "artifacts/dsp-a/token.txt", "sha256": sha(b"ABCD")}]}


def claim(**spec_extra):
    return {"task_id": "task-b", "dispatch_id": "dsp-b", "attempt": 1, "ttl_s": 30,
            "spec": {"adapter": "synthetic", "params": {"write": "o.txt", "from_input": "reverse"},
                     "effect_key": "cfx-" + "0" * 40, **spec_extra}}


def test_resolve_spec_carries_a_valid_input_and_none_for_an_independent_task(tmp_path):
    with_input = worker_service.resolve_spec(claim(input=GOOD_INPUT), "w1", str(tmp_path / "artifacts"), 1.0,
                                             home=str(tmp_path))
    assert with_input.input == GOOD_INPUT
    assert worker_service.resolve_spec(claim(), "w1", str(tmp_path / "artifacts"), 1.0, home=str(tmp_path)).input is None


@pytest.mark.parametrize("bad", [
    "text",
    {**GOOD_INPUT, "extra": 1},
    {k: v for k, v in GOOD_INPUT.items() if k != "result_id"},
    {**GOOD_INPUT, "task_id": ""},
    {**GOOD_INPUT, "artifacts": []},
    {**GOOD_INPUT, "artifacts": [{"path": "../outside.txt", "sha256": sha(b"x")}]},
    {**GOOD_INPUT, "artifacts": [{"path": "C:/abs.txt", "sha256": sha(b"x")}]},
    {**GOOD_INPUT, "artifacts": [{"path": "a\\b.txt", "sha256": sha(b"x")}]},
    {**GOOD_INPUT, "artifacts": [{"path": "/abs.txt", "sha256": sha(b"x")}]},
    {**GOOD_INPUT, "artifacts": [{"path": "artifacts/x.txt", "sha256": "not-a-hash"}]},
])
def test_a_malformed_input_refuses_the_claim_before_it_runs(bad, tmp_path):
    with pytest.raises(SpecError):
        worker_service.resolve_spec(claim(input=bad), "w1", str(tmp_path / "artifacts"), 1.0, home=str(tmp_path))


def test_write_request_adds_input_and_home_only_for_a_dependent_task(tmp_path):
    base = dict(adapter="synthetic", params={}, attempt=1, task_id="t", effect_key="k",
                artifact_dir=str(tmp_path / "artifacts" / "d"))
    plain = json.loads(Path(adapter_bridge.write_request(str(tmp_path), SimpleNamespace(dispatch_id="d1", **base))).read_text())
    assert set(plain) == {"adapter", "params", "attempt", "task_id", "dispatch_id", "effect_key", "workdir", "report"}
    bound = json.loads(Path(adapter_bridge.write_request(
        str(tmp_path), SimpleNamespace(dispatch_id="d2", input=GOOD_INPUT, **base))).read_text())
    assert bound["input"] == GOOD_INPUT and Path(bound["home"]) == tmp_path.resolve()


# ----------------------------------------------------------------- L3: runner
def runner_request(tmp_path, digest, transform="reverse"):
    (tmp_path / "artifacts" / "dsp-a").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts" / "dsp-a" / "token.txt").write_bytes(b"ABCD")
    request = {"adapter": "synthetic", "params": {"write": "o.txt", "from_input": transform}, "attempt": 1,
               "task_id": "task-b", "dispatch_id": "dsp-b", "effect_key": "k",
               "workdir": str(tmp_path / "artifacts" / "dsp-b"), "report": str(tmp_path / "run" / "reports" / "dsp-b.json"),
               "home": str(tmp_path.resolve()),
               "input": {**GOOD_INPUT, "artifacts": [{"path": "artifacts/dsp-a/token.txt", "sha256": digest}]}}
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    return path, request


def test_runner_hands_the_hash_checked_input_to_the_adapter(tmp_path):
    path, request = runner_request(tmp_path, sha(b"ABCD"))
    assert adapter_runner.main([str(path)]) == 0
    assert json.loads(Path(request["report"]).read_text())["outcome"] == "success"
    assert (Path(request["workdir"]) / "o.txt").read_bytes() == b"DCBA"


def test_runner_refuses_an_input_whose_bytes_do_not_match_the_verified_hash(tmp_path):
    path, request = runner_request(tmp_path, sha(b"something else"))
    assert adapter_runner.main([str(path)]) == 0
    report = json.loads(Path(request["report"]).read_text())
    assert report["outcome"] == "failure" and report["retryable"] is False and "input refused" in report["reason"]
    assert not (Path(request["workdir"]) / "o.txt").exists()


# ------------------------------------------------------- L4: adapter and verifier
def test_synthetic_from_input_params():
    assert synthetic.transform_input("reverse", b"ABCD") == b"DCBA"
    assert synthetic.transform_input("copy", b"ABCD") == b"ABCD"
    with pytest.raises(synthetic.SyntheticError):
        synthetic._params({"from_input": "uppercase"})
    with pytest.raises(synthetic.SyntheticError):
        synthetic._params({"from_input": "reverse", "content": "fixed"})


def test_synthetic_from_input_needs_an_input(tmp_path):
    with pytest.raises(synthetic.SyntheticError):
        synthetic.run({"from_input": "reverse"}, tmp_path)


def verify_case(tmp_path, produced=b"DCBA", bound="default", source=b"ABCD"):
    (tmp_path / "artifacts" / "dsp-a").mkdir(parents=True)
    (tmp_path / "artifacts" / "dsp-a" / "token.txt").write_bytes(source)
    (tmp_path / "artifacts" / "dsp-b").mkdir(parents=True)
    (tmp_path / "artifacts" / "dsp-b" / "o.txt").write_bytes(produced)
    if bound == "default":
        bound = GOOD_INPUT
    task = SimpleNamespace(params={"write": "o.txt", "from_input": "reverse"}, dispatch_id="dsp-b",
                           effect_class="idempotent", input=bound)
    result = SimpleNamespace(dispatch_id="dsp-b", payload={
        "outcome": "success", "artifacts": [{"path": "artifacts/dsp-b/o.txt", "sha256": sha(produced)}]})
    return synthetic.verify(task, result, tmp_path)


def test_verifier_accepts_the_transform_of_the_verified_input(tmp_path):
    verdict = verify_case(tmp_path)
    assert verdict.accepted, verdict.reason


def test_verifier_rejects_a_wrong_output(tmp_path):
    verdict = verify_case(tmp_path, produced=b"DCBX")
    assert not verdict.accepted and "transformed input" in verdict.reason


def test_verifier_rejects_when_the_input_artifact_was_changed(tmp_path):
    verdict = verify_case(tmp_path, produced=b"LIVE", source=b"EVIL")
    assert not verdict.accepted and "no longer matches" in verdict.reason


def test_verifier_rejects_a_from_input_task_without_a_bound_input(tmp_path):
    verdict = verify_case(tmp_path, bound=None)
    assert not verdict.accepted and "no verified input" in verdict.reason
