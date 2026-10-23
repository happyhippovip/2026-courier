"""Synthetic A→B→C canary: GOOGLE_WINDOWS verifies A, MUSE_MAC takes B, then C.

SYNTHETIC_VERIFIED only. REAL_PROVIDER stays NOT_TESTED. Cost stays 0 EUR.
The mission chip is a separate hub surface and is not written by this bridge.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from courier_core.controller import ApiError, Controller
from courier_core.events import EventType
from courier_core.state_machine import RESOLVED_VERIFIED, TaskStatus
from courier_core.verification import Verdict
from scripts.coordination_ledger import MissionStatus
from scripts.coordination_resume import CONFLICT, claim_mission, reduce_store
from scripts.coordination_ledger import AgentID, HostID
from scripts.github_coordination import FileCoordinationStore
from tests.test_cross_host_handoff import MAC, MAC_HOST, _mac_ready, _run
from tests.test_ledger_v1_bridge import AGENT, HOST, FakeHTTP, _home, _ready, _seed, _spec


class ResultHTTP(FakeHTTP):
    """FakeHTTP plus verified result bodies, and one death after a post is accepted."""

    def __init__(self):
        super().__init__()
        self.results = {}
        self.kill_get_after_post = False
        self._arm_kill = False

    def __call__(self, method, url, headers, body, timeout):
        if method == "GET" and url.rstrip("/").endswith("/result"):
            task_id = url.rstrip("/").rsplit("/", 2)[-2]
            result = self.results.get(task_id)
            if result is None:
                return 409, b'{"error":"not_verified"}'
            return 200, json.dumps(result).encode()
        if method == "POST" and url.endswith("/v1/tasks") and self.kill_get_after_post:
            self.kill_get_after_post = False
            self._arm_kill = True
            return super().__call__(method, url, headers, body, timeout)
        if method == "GET" and self._arm_kill:
            self._arm_kill = False
            raise OSError("killed after accept")
        return super().__call__(method, url, headers, body, timeout)


def _mac_unit(unit, inputs_from=None):
    body = _spec(
        params={"unit": unit},
        agent_id=MAC,
        host_id=MAC_HOST,
        estimated_cost_eur=0.0,
    )
    if inputs_from is not None:
        body["inputs_from"] = inputs_from
    return body


def _chain(tmp_path):
    http = ResultHTTP()
    home = _home(tmp_path, {
        "A": _spec(),
        "B": _mac_unit("b"),
        "C": _mac_unit("c", ["B"]),
    })
    _seed(home, [
        _ready("A", "a-assign", "2026-10-23T08:00:00Z"),
        _mac_ready("B", "b-assign", "2026-10-23T08:00:01Z", deps=["A"]),
        _mac_ready("C", "c-assign", "2026-10-23T08:00:02Z", deps=["B"]),
    ])
    return http, home


def _task_id(posted):
    return "task-" + hashlib.sha256(posted["idempotency_key"].encode("utf-8")).hexdigest()[:32]


def _verify(http, task_id, result_id, resolution="verified"):
    http.views[task_id].update({
        "status": "COMPLETE",
        "attempt": 1,
        "accepted_result_id": result_id,
        "resolution": resolution,
    })


def _plant(home, http, task_id, result_id, payload):
    path = f"artifacts/canary/{task_id}.txt"
    target = home / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    http.results[task_id] = {
        "task_id": task_id,
        "result_id": result_id,
        "artifacts": [{"path": path, "sha256": digest}],
    }
    return path, digest


def _state(home):
    return json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))


def _reducer(home):
    return reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))


def _windows_verifies_a(http, home):
    code, out, err = _run(home, http, AGENT, HOST)
    assert code == 0, err
    assert len(http.posts) == 1
    task_a = _task_id(http.posts[0])
    _verify(http, task_a, "result-a")
    code, out, err = _run(home, http, AGENT, HOST)
    assert code == 0, err
    assert '"outcome":"final"' in out
    assert len(http.posts) == 1
    return task_a


def _mac_posts_b(http, home):
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 0, err
    assert len(http.posts) == 2
    assert http.posts[1]["params"]["unit"] == "b"
    assert '"proof":"SYNTHETIC"' in out
    assert '"owner":"MUSE_MAC"' in out
    assert out.count('"outcome":"queued"') == 1
    return _task_id(http.posts[1])


def test_abc_canary_posts_c_only_after_b_is_verified(tmp_path):
    http, home = _chain(tmp_path)
    _windows_verifies_a(http, home)
    task_b = _mac_posts_b(http, home)

    _verify(http, task_b, "result-b", resolution=None)
    http.views[task_b].pop("resolution", None)
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 2, err
    assert "evidence_missing" in out
    assert len(http.posts) == 2
    assert "C" not in _state(home)["missions"]
    assert _reducer(home).get_mission("C")["status"] == MissionStatus.WORKING

    _verify(http, task_b, "result-b")
    path, digest = _plant(home, http, task_b, "result-b", b"from-b")
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 0, err
    assert len(http.posts) == 3
    assert http.posts[2]["params"]["unit"] == "c"
    assert http.posts[2]["params"]["inputs"] == [{
        "mission_id": "B",
        "task_id": task_b,
        "result_id": "result-b",
        "path": path,
        "sha256": digest,
    }]
    assert '"proof":"SYNTHETIC"' in out
    assert '"owner":"MUSE_MAC"' in out

    replay_code, replay_out, replay_err = _run(home, http, MAC, MAC_HOST)
    assert replay_code == 0, replay_err
    assert len(http.posts) == 3
    assert replay_out.count('"outcome":"queued"') == 0

    win_code, _, win_err = _run(home, http, AGENT, HOST)
    assert win_code == 0, win_err
    assert len(http.posts) == 3
    stolen = claim_mission(
        FileCoordinationStore(home / "coordination_ledger.jsonl"),
        AgentID.GOOGLE_WINDOWS,
        HostID.WINDOWS_REMOTE,
        "C",
    )
    assert stolen.outcome == CONFLICT

    reducer = _reducer(home)
    assert reducer.get_mission("A")["status"] == MissionStatus.DONE
    assert reducer.get_mission("B")["status"] == MissionStatus.DONE
    assert reducer.get_mission("C")["status"] == MissionStatus.WORKING
    missions = _state(home)["missions"]
    assert missions["A"]["status"] == "FINAL_DONE"
    assert missions["B"]["status"] == "FINAL_DONE"
    assert missions["C"]["status"] == "POSTED"
    assert missions["C"]["status"] != "FINAL_DONE"


def test_tampered_b_blocks_c(tmp_path):
    http, home = _chain(tmp_path)
    _windows_verifies_a(http, home)
    task_b = _mac_posts_b(http, home)
    path, digest = _plant(home, http, task_b, "result-b", b"from-b")
    (home / path).write_bytes(b"tampered")
    assert hashlib.sha256((home / path).read_bytes()).hexdigest() != digest
    _verify(http, task_b, "result-b")

    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 2, err
    assert "input_digest_mismatch" in out
    assert len(http.posts) == 2
    assert "C" not in _state(home)["missions"]
    reducer = _reducer(home)
    assert reducer.get_mission("B")["status"] == MissionStatus.DONE
    assert reducer.get_mission("C")["status"] == MissionStatus.WORKING
    assert reducer.get_mission("C")["status"] != MissionStatus.DONE


def test_mac_offline_after_accept_does_not_complete_or_repost(tmp_path):
    http, home = _chain(tmp_path)
    _windows_verifies_a(http, home)
    task_b = _mac_posts_b(http, home)
    marker = home / "hosts"
    marker.mkdir()
    (marker / "MAC_LOCAL.offline").write_text("synthetic-offline\n", encoding="utf-8")
    _verify(http, task_b, "result-b")
    path, _digest = _plant(home, http, task_b, "result-b", b"from-b")

    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 2, err
    assert "target_host_unavailable" in out
    assert '"proof":"SYNTHETIC"' in out
    assert len(http.posts) == 2
    assert _reducer(home).get_mission("B")["status"] == MissionStatus.WORKING
    assert _reducer(home).get_mission("B")["status"] != MissionStatus.DONE
    assert "C" not in _state(home)["missions"]

    (marker / "MAC_LOCAL.offline").unlink()
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 0, err
    assert len(http.posts) == 3
    assert http.posts[2]["params"]["inputs"][0]["path"] == path
    assert _reducer(home).get_mission("B")["status"] == MissionStatus.DONE
    assert _state(home)["missions"]["B"]["posted"] is True
    assert _state(home)["missions"]["C"]["status"] == "POSTED"


def test_sender_dies_before_mac_accept_then_retries_same_key(tmp_path):
    http, home = _chain(tmp_path)
    _windows_verifies_a(http, home)
    http.fail_post = True
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 75
    assert "controller unreachable" in err
    assert len(http.posts) == 1
    assert _state(home)["missions"]["B"]["posted"] is False
    key = _state(home)["missions"]["B"]["idempotency_key"]
    assert "C" not in _state(home)["missions"]

    http.fail_post = False
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 0, err
    assert len(http.posts) == 2
    assert http.posts[1]["idempotency_key"] == key
    assert _state(home)["missions"]["B"]["posted"] is True
    started = [
        json.loads(line) for line in (home / "coordination_ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if '"STARTED"' in line and '"mission_id": "B"' in line or '"mission_id":"B"' in line and '"STARTED"' in line
    ]
    assert len(started) == 1


def test_sender_dies_after_mac_accept_then_replays_without_a_second_task(tmp_path):
    http, home = _chain(tmp_path)
    _windows_verifies_a(http, home)
    http.kill_get_after_post = True
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 75
    assert "controller unreachable" in err
    assert len(http.posts) == 2
    assert _state(home)["missions"]["B"]["posted"] is False
    key = http.posts[1]["idempotency_key"]

    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 0, err
    assert len(http.posts) == 2
    assert http.posts[1]["idempotency_key"] == key
    assert '"outcome":"duplicate"' in out
    assert _state(home)["missions"]["B"]["posted"] is True
    assert "C" not in _state(home)["missions"]
    replay_code, replay_out, replay_err = _run(home, http, MAC, MAC_HOST)
    assert replay_code == 0, replay_err
    assert len(http.posts) == 2
    assert replay_out.count('"outcome":"queued"') == 0
    assert replay_out.count('"outcome":"duplicate"') == 0


def _final_rows(home, mission_id):
    rows = []
    path = home / "coordination_ledger.jsonl"
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("mission_id") == mission_id and row.get("event_type") == "FINAL":
            rows.append(row)
    return rows


def _assert_final_evidence(home, mission_id, task_id, result_id):
    rows = _final_rows(home, mission_id)
    assert len(rows) == 1
    evidence = rows[0]["evidence_ref"]
    assert f"task_id={task_id}" in evidence
    assert f"accepted_result_id={result_id}" in evidence
    assert "attempt=1" in evidence
    return evidence


def test_abc_canary_final_evidence_names_the_verified_task_and_attempt(tmp_path):
    """A, B, and C in one run. FINAL only after that mission's verified result."""
    http, home = _chain(tmp_path)
    task_a = _windows_verifies_a(http, home)
    _assert_final_evidence(home, "A", task_a, "result-a")
    assert _final_rows(home, "B") == [] and _final_rows(home, "C") == []

    task_b = _mac_posts_b(http, home)
    assert _state(home)["missions"]["B"]["status"] == "POSTED"
    assert _final_rows(home, "B") == []
    _verify(http, task_b, "result-b")
    path_b, _digest_b = _plant(home, http, task_b, "result-b", b"from-b")
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 0, err
    _assert_final_evidence(home, "B", task_b, "result-b")
    task_c = _task_id(http.posts[2])
    assert http.posts[2]["params"]["inputs"][0]["path"] == path_b
    assert _state(home)["missions"]["C"]["status"] == "POSTED"
    assert _final_rows(home, "C") == []

    _verify(http, task_c, "result-c")
    _plant(home, http, task_c, "result-c", b"from-c")
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 0, err
    _assert_final_evidence(home, "C", task_c, "result-c")
    assert _state(home)["missions"]["C"]["status"] == "FINAL_DONE"
    assert _reducer(home).get_mission("C")["status"] == MissionStatus.DONE

    replay_code, _, replay_err = _run(home, http, MAC, MAC_HOST)
    assert replay_code == 0, replay_err
    assert len(http.posts) == 3
    assert len(_final_rows(home, "A")) == len(_final_rows(home, "B")) == len(_final_rows(home, "C")) == 1


def test_missing_upstream_bytes_do_not_finalise_c(tmp_path):
    http, home = _chain(tmp_path)
    _windows_verifies_a(http, home)
    task_b = _mac_posts_b(http, home)
    path, _digest = _plant(home, http, task_b, "result-b", b"from-b")
    (home / path).unlink()
    _verify(http, task_b, "result-b")
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 2, err
    assert "input_digest_mismatch" in out
    assert len(http.posts) == 2
    assert "C" not in _state(home)["missions"]
    assert _final_rows(home, "C") == []
    assert _reducer(home).get_mission("C")["status"] != MissionStatus.DONE


def test_wrong_upstream_hash_does_not_finalise_c(tmp_path):
    http, home = _chain(tmp_path)
    _windows_verifies_a(http, home)
    task_b = _mac_posts_b(http, home)
    path = f"artifacts/canary/{task_b}.txt"
    target = home / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"from-b")
    http.results[task_b] = {
        "task_id": task_b,
        "result_id": "result-b",
        "artifacts": [{"path": path, "sha256": hashlib.sha256(b"other").hexdigest()}],
    }
    _verify(http, task_b, "result-b")
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 2, err
    assert "input_digest_mismatch" in out
    assert len(http.posts) == 2
    assert _final_rows(home, "C") == []
    assert _state(home)["missions"].get("C", {}).get("status") != "FINAL_DONE"


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _journal(tmp_path):
    home = tmp_path / "home"

    def verify(task, result, root):
        arts = result.payload.get("artifacts") or []
        if len(arts) != 1 or not isinstance(arts[0], dict):
            return Verdict(False, "missing artifact")
        art = arts[0]
        target = root / art.get("path", "")
        if not target.is_file():
            return Verdict(False, "missing bytes")
        if art.get("sha256") != hashlib.sha256(target.read_bytes()).hexdigest():
            return Verdict(False, "wrong hash")
        upstream = task.params.get("input_sha256")
        upstream_path = task.params.get("input_path")
        if upstream is not None:
            source = root / upstream_path
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != upstream:
                return Verdict(False, "stale input")
        return Verdict(True, "bytes match")

    ctrl = Controller(home, verifier=lambda _adapter: verify, clock=_Clock()).boot()
    return ctrl, home


def _accepted(ctrl, task_id):
    return [e for e in ctrl.journal.events(task_id=task_id) if e.type is EventType.RESULT_ACCEPTED]


def _finish(ctrl, home, name, payload, dependency=None, input_path=None, input_sha=None, write=True, digest=None):
    params = {"estimated_cost_eur": 0.0, "unit": name}
    if input_sha is not None:
        params["input_sha256"] = input_sha
        params["input_path"] = input_path
    body = {
        "adapter": "synthetic",
        "params": params,
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
        "idempotency_key": f"canary:{name}",
    }
    if dependency is not None:
        body["depends_on"] = dependency
    _status, created = ctrl.create_task(body)
    task_id = created["task_id"]
    assert _accepted(ctrl, task_id) == []
    claim = ctrl.claim({"worker_id": "w1"})
    assert claim is not None and claim["task_id"] == task_id and claim["attempt"] == 1
    if dependency is not None:
        assert claim["spec"]["input"]["task_id"] == dependency
    ctrl.start({"dispatch_id": claim["dispatch_id"], "worker_id": "w1"})
    rel = f"artifacts/canary/{name}.txt"
    if write:
        target = home / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    declared = digest if digest is not None else hashlib.sha256(payload).hexdigest()
    ctrl.result({
        "dispatch_id": claim["dispatch_id"],
        "result_id": f"result-{name}",
        "outcome": "success",
        "artifacts": [{"path": rel, "sha256": declared}],
    })
    ctrl.drain()
    return task_id, rel, declared, claim["dispatch_id"]


def test_abc_journal_accepts_each_task_on_its_own_attempt(tmp_path):
    """One synthetic chain. RESULT_ACCEPTED names that task, attempt, and dispatch."""
    ctrl, home = _journal(tmp_path)
    try:
        task_a, path_a, digest_a, dispatch_a = _finish(ctrl, home, "A", b"alpha")
        accepted_a = _accepted(ctrl, task_a)
        assert len(accepted_a) == 1
        assert accepted_a[0].attempt == 1 and accepted_a[0].dispatch_id == dispatch_a
        assert accepted_a[0].result_id == "result-A"
        assert ctrl.journal.task(task_a).status is TaskStatus.COMPLETE
        assert ctrl.journal.task(task_a).resolution == RESOLVED_VERIFIED

        assert ctrl.claim({"worker_id": "w1"}) is None  # B does not exist yet; nothing else is queued
        task_b, path_b, digest_b, dispatch_b = _finish(
            ctrl, home, "B", b"bravo", dependency=task_a, input_path=path_a, input_sha=digest_a,
        )
        accepted_b = _accepted(ctrl, task_b)
        assert len(accepted_b) == 1 and accepted_b[0].attempt == 1 and accepted_b[0].dispatch_id == dispatch_b
        assert accepted_b[0].task_id == task_b and accepted_b[0].result_id == "result-B"
        assert _accepted(ctrl, task_a) == accepted_a  # B's proof does not accept A again

        task_c, _path_c, _digest_c, dispatch_c = _finish(
            ctrl, home, "C", b"charlie", dependency=task_b, input_path=path_b, input_sha=digest_b,
        )
        accepted_c = _accepted(ctrl, task_c)
        assert len(accepted_c) == 1
        assert accepted_c[0].task_id == task_c and accepted_c[0].attempt == 1
        assert accepted_c[0].dispatch_id == dispatch_c and accepted_c[0].result_id == "result-C"
        assert ctrl.journal.task(task_c).resolution == RESOLVED_VERIFIED
        assert [e.result_id for e in accepted_a + accepted_b + accepted_c] == ["result-A", "result-B", "result-C"]
    finally:
        ctrl.stop()


def test_missing_bytes_and_wrong_hash_are_not_accepted(tmp_path):
    ctrl, home = _journal(tmp_path)
    try:
        missing, *_rest = _finish(ctrl, home, "missing", b"gone", write=False)
        assert _accepted(ctrl, missing) == []
        assert ctrl.journal.task(missing).status is not TaskStatus.COMPLETE

        mismatched, *_rest = _finish(
            ctrl, home, "mismatch", b"real", digest=hashlib.sha256(b"other").hexdigest(),
        )
        assert _accepted(ctrl, mismatched) == []
        assert ctrl.journal.task(mismatched).resolution != RESOLVED_VERIFIED
    finally:
        ctrl.stop()


def test_stale_upstream_bytes_do_not_accept_the_dependent(tmp_path):
    ctrl, home = _journal(tmp_path)
    try:
        task_a, path_a, digest_a, _dispatch_a = _finish(ctrl, home, "A", b"alpha")
        (home / path_a).write_bytes(b"replaced")
        task_b, *_rest = _finish(
            ctrl, home, "B", b"bravo", dependency=task_a, input_path=path_a, input_sha=digest_a,
        )
        assert _accepted(ctrl, task_b) == []
        assert ctrl.journal.task(task_a).resolution == RESOLVED_VERIFIED
        assert ctrl.journal.task(task_b).resolution != RESOLVED_VERIFIED
        assert ctrl.claim({"worker_id": "w1"}) is None
    finally:
        ctrl.stop()


def test_stale_dispatch_does_not_accept_a_result(tmp_path):
    clock = _Clock()
    ctrl = Controller(tmp_path / "home", verifier=lambda _adapter: (lambda *_a: Verdict(True, "unused")), clock=clock).boot()
    try:
        _status, created = ctrl.create_task({
            "adapter": "synthetic",
            "params": {"estimated_cost_eur": 0.0, "unit": "stale"},
            "effect_class": "non_idempotent",
            "max_attempts": 1,
            "lease_ttl_s": 10,
            "idempotency_key": "canary:stale",
        })
        task_id = created["task_id"]
        old = ctrl.claim({"worker_id": "w1"})
        ctrl.start({"dispatch_id": old["dispatch_id"], "worker_id": "w1"})
        clock.t += 11
        ctrl.tick()
        assert ctrl.journal.task(task_id).status is TaskStatus.BLOCKED
        ctrl.resolve(task_id, {
            "decision": "retry_authorized",
            "actor": "desk:ana",
            "attempt": 1,
            "reason": "synthetic retry of a lost attempt",
        })
        fresh = ctrl.claim({"worker_id": "w2"})
        assert fresh["attempt"] == 2 and fresh["dispatch_id"] != old["dispatch_id"]
        with pytest.raises(ApiError) as info:
            ctrl.result({
                "dispatch_id": old["dispatch_id"],
                "result_id": "stale-result",
                "outcome": "success",
                "artifacts": [{"path": "artifacts/canary/stale.txt", "sha256": hashlib.sha256(b"stale").hexdigest()}],
            })
        assert info.value.code == "stale_dispatch"
        assert _accepted(ctrl, task_id) == []
        assert ctrl.journal.task(task_id).resolution != RESOLVED_VERIFIED
    finally:
        ctrl.stop()
