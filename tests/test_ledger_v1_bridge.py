"""Ledger mission to V1 controller task. Injected HTTP only; no providers."""

import hashlib
import json
import subprocess
from pathlib import Path

from scripts.coordination_ledger import (
    AgentID, CoordinationEvent, EventType, HostID, MissionStatus,
)
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore
from scripts.ledger_v1_bridge import _load_state, main

TOKEN = "controller-token-value-0123456789abcdef"
AGENT = "GOOGLE_WINDOWS"
HOST = "WINDOWS_REMOTE"
REPO = Path(__file__).resolve().parents[1]
SHA = "0123456789abcdef0123456789abcdef01234567"


def _event(eid, mid, etype, status, ts, deps=None):
    return CoordinationEvent(
        event_id=eid, mission_id=mid, agent_id=AgentID.GOOGLE_WINDOWS, host_id=HostID.WINDOWS_REMOTE,
        event_type=etype, status=status, depends_on=deps or [], head="sha", evidence_ref="ref",
        created_at=ts, payload_hash="h", ownership=AGENT,
    )


def _spec(**overrides):
    body = {
        "adapter": "synthetic",
        "params": {"unit": "a"},
        "effect_class": "idempotent",
        "max_attempts": 1,
        "lease_ttl_s": 30,
    }
    body.update(overrides)
    return body


class FakeHTTP:
    def __init__(self):
        self.posts = []
        self.views = {}
        self.fail_post = False
        self.down = False

    def __call__(self, method, url, headers, body, timeout):
        assert timeout > 0
        assert TOKEN not in url
        assert "Bearer" not in url
        if "127.0.0.1" in url or "[::1]" in url or "localhost" in url:
            assert headers.get("X-Courier-Token") == TOKEN
        if self.down or (method == "POST" and self.fail_post):
            raise OSError("controller unreachable")
        if method == "POST" and url.endswith("/v1/tasks"):
            posted = json.loads(body.decode("utf-8"))
            key = posted["idempotency_key"]
            task_id = "task-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
            duplicate = any(item["idempotency_key"] == key for item in self.posts)
            if not duplicate:
                self.posts.append(posted)
                self.views.setdefault(task_id, {
                    "task_id": task_id, "status": "QUEUED", "attempt": 0,
                    "accepted_result_id": None, "last_reason": None,
                })
            return (200 if duplicate else 201), json.dumps(
                {"task_id": task_id, "duplicate": duplicate}).encode()
        if method == "GET" and "/v1/tasks/" in url:
            task_id = url.rstrip("/").rsplit("/", 1)[-1]
            view = self.views.get(task_id)
            if view is None:
                return 404, b'{"error":"unknown_task"}'
            return 200, json.dumps(view).encode()
        raise AssertionError(url)


def _home(tmp_path, specs):
    home = tmp_path / "home"
    (home / "run").mkdir(parents=True)
    (home / "run" / "controller.token").write_text(TOKEN + "\n", encoding="utf-8")
    if specs is not None:
        (home / "ledger_tasks.json").write_text(json.dumps(specs), encoding="utf-8")
    return home


def _seed(home, events):
    store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    for event in events:
        store.write_event(event)
    return store


def _run(home, http, *, extra=None):
    out, err = [], []
    code = main(
        [
            "--home", str(home),
            "--agent-id", AGENT,
            "--host-id", HOST,
            "--controller", "http://127.0.0.1:9",
            *(extra or []),
        ],
        http=http,
        stdout=out.append,
        stderr=err.append,
    )
    log_path = home / "run" / "ledger_bridge.log"
    log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    ledger = home / "coordination_ledger.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines() if ledger.exists() else []
    return code, "".join(out), "".join(err), log, lines


def _ready(mid, eid, ts="2026-10-08T04:00:00Z", deps=None):
    return _event(eid, mid, EventType.ASSIGNED, MissionStatus.WORKING, ts, deps)


def _git_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()


def _mapped(task_id="task-a", claim="claim-a", fingerprint="fp", source=SHA, attempt=1):
    return {
        "task_id": task_id,
        "claim_event_id": claim,
        "idempotency_key": "ledger:" + claim,
        "posted": True,
        "accepted_result_id": None,
        "attempt": attempt,
        "spec_fingerprint": fingerprint,
        "source_sha": source,
        "evidence_ref": "seed",
    }


def test_ready_mission_is_claimed_and_posted_once(tmp_path):
    http = FakeHTTP()
    home = _home(tmp_path, {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    code, out, err, log, lines = _run(home, http)
    assert code == 0
    assert len(http.posts) == 1
    posted = http.posts[0]
    assert posted["idempotency_key"].startswith("ledger:claim-")
    assert posted["adapter"] == "synthetic"
    assert posted["params"] == {"unit": "a"}
    assert posted["effect_class"] == "idempotent"
    assert posted["max_attempts"] == 1
    assert posted["lease_ttl_s"] == 30
    assert "source_sha" not in posted
    assert sum(1 for line in lines if '"event_type": "STARTED"' in line or '"event_type":"STARTED"' in line) == 1
    record = json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))["missions"]["A"]
    assert record["posted"] is True
    assert record["task_id"].startswith("task-")
    assert record["accepted_result_id"] is None
    assert record["attempt"] == 0
    assert len(record["spec_fingerprint"]) == 64
    assert record["source_sha"] == _git_head()
    evidence = record["evidence_ref"]
    assert record["task_id"] in evidence
    assert "accepted_result_id=none" in evidence
    assert "attempt=0" in evidence
    assert record["spec_fingerprint"] in evidence
    assert record["source_sha"] in evidence
    assert "queued" in out


def test_replay_writes_nothing_and_posts_nothing(tmp_path):
    http = FakeHTTP()
    home = _home(tmp_path, {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    assert _run(home, http)[0] == 0
    before = (home / "coordination_ledger.jsonl").read_text(encoding="utf-8")
    code, out, err, log, lines = _run(home, http)
    assert code == 0
    assert len(http.posts) == 1
    assert (home / "coordination_ledger.jsonl").read_text(encoding="utf-8") == before


def test_post_failure_after_claim_retries_same_key(tmp_path):
    http = FakeHTTP()
    http.fail_post = True
    home = _home(tmp_path, {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    code, *_ = _run(home, http)
    assert code == 75
    assert http.posts == []
    claim_lines = [ln for ln in (home / "coordination_ledger.jsonl").read_text(encoding="utf-8").splitlines()
                   if '"STARTED"' in ln]
    assert len(claim_lines) == 1
    http.fail_post = False
    code2, *_ = _run(home, http)
    assert code2 == 0
    assert len(http.posts) == 1
    again = [ln for ln in (home / "coordination_ledger.jsonl").read_text(encoding="utf-8").splitlines()
             if '"STARTED"' in ln]
    assert again == claim_lines
    assert http.posts[0]["idempotency_key"].startswith("ledger:claim-")


def test_complete_a_finalizes_and_posts_b_in_the_same_pass(tmp_path):
    http = FakeHTTP()
    home = _home(tmp_path, {"A": _spec(), "B": _spec(params={"unit": "b"})})
    _seed(home, [
        _ready("A", "a-assign", "2026-10-08T04:00:00Z"),
        _ready("B", "b-assign", "2026-10-08T04:00:01Z", deps=["A"]),
    ])
    assert _run(home, http)[0] == 0
    assert len(http.posts) == 1
    assert http.posts[0]["params"] == {"unit": "a"}
    task_id = "task-" + hashlib.sha256(http.posts[0]["idempotency_key"].encode()).hexdigest()[:32]
    http.views[task_id]["status"] = "COMPLETE"
    http.views[task_id]["accepted_result_id"] = "result-a"
    http.views[task_id]["attempt"] = 1
    record = json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))["missions"]["A"]
    before = len((home / "coordination_ledger.jsonl").read_text(encoding="utf-8").splitlines())
    code, out, err, log, lines = _run(home, http)
    assert code == 0
    assert len(http.posts) == 2
    assert http.posts[1]["params"] == {"unit": "b"}
    assert http.posts[1]["idempotency_key"].startswith("ledger:claim-")
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    assert reducer.get_mission("A")["status"] == MissionStatus.DONE
    final = [e for e in reducer.events if e.event_type == EventType.FINAL]
    assert len(final) == 1
    assert final[0].event_id.startswith("final-")
    assert task_id in final[0].evidence_ref
    assert "accepted_result_id=result-a" in final[0].evidence_ref
    assert "attempt=1" in final[0].evidence_ref
    assert record["spec_fingerprint"] in final[0].evidence_ref
    assert record["source_sha"] in final[0].evidence_ref
    assert final[0].payload_hash == hashlib.sha256(final[0].evidence_ref.encode("utf-8")).hexdigest()
    assert len(lines) == before + 2  # FINAL for A, claim for B
    assert "final" in out


def test_blocked_a_parks_and_unrelated_c_dispatches(tmp_path):
    http = FakeHTTP()
    home = _home(tmp_path, {"A": _spec(), "C": _spec(params={"unit": "c"})})
    _seed(home, [
        _ready("A", "a-assign"),
        _ready("C", "c-assign", "2026-10-08T04:00:01Z"),
    ])
    state = {
        "missions": {
            "A": _mapped(claim="claim-already"),
        }
    }
    (home / "ledger_bridge_state.json").write_text(json.dumps(state), encoding="utf-8")
    http.views["task-a"] = {
        "task_id": "task-a", "status": "BLOCKED", "attempt": 2,
        "accepted_result_id": None, "last_reason": "needs a person",
    }
    code, out, err, log, lines = _run(home, http)
    assert code == 0
    assert len(http.posts) == 1
    assert http.posts[0]["params"] == {"unit": "c"}
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    assert reducer.get_mission("A")["status"] == MissionStatus.BLOCKED
    assert reducer.get_mission("A")["blocker"] == "needs a person"
    blocked = [e for e in reducer.events if e.event_type == EventType.BLOCKED]
    assert len(blocked) == 1
    assert "task_id=task-a" in blocked[0].evidence_ref
    assert "attempt=2" in blocked[0].evidence_ref
    assert "spec_fingerprint=fp" in blocked[0].evidence_ref
    assert f"source_sha={SHA}" in blocked[0].evidence_ref
    assert not any(e.event_type == EventType.FINAL for e in reducer.events)


def test_failed_or_cancelled_becomes_error_not_final(tmp_path):
    for status in ("FAILED", "CANCELLED"):
        http = FakeHTTP()
        home = _home(tmp_path / status, {"A": _spec()})
        _seed(home, [_ready("A", "a-assign")])
        (home / "ledger_bridge_state.json").write_text(
            json.dumps({"missions": {"A": _mapped()}}), encoding="utf-8")
        http.views["task-a"] = {
            "task_id": "task-a", "status": status, "attempt": 1,
            "accepted_result_id": None, "last_reason": "boom",
        }
        code, out, err, log, lines = _run(home, http)
        assert code == 0 and http.posts == []
        reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
        assert reducer.get_mission("A")["status"] == MissionStatus.ERROR
        errors = [e for e in reducer.events if e.event_type == EventType.ERROR]
        assert len(errors) == 1
        assert "task_id=task-a" in errors[0].evidence_ref
        assert "attempt=1" in errors[0].evidence_ref
        assert f"source_sha={SHA}" in errors[0].evidence_ref
        assert not any(e.event_type == EventType.FINAL for e in reducer.events)
        before = (home / "coordination_ledger.jsonl").read_text(encoding="utf-8")
        assert _run(home, http)[0] == 0
        assert http.posts == []
        assert (home / "coordination_ledger.jsonl").read_text(encoding="utf-8") == before


def test_restart_on_complete_task_writes_one_final_and_no_post(tmp_path):
    http = FakeHTTP()
    home = _home(tmp_path, {"A": _spec(source_sha=SHA)})
    _seed(home, [_ready("A", "a-assign")])
    (home / "ledger_bridge_state.json").write_text(
        json.dumps({"missions": {"A": _mapped()}}), encoding="utf-8")
    http.views["task-a"] = {
        "task_id": "task-a", "status": "COMPLETE", "attempt": 1,
        "accepted_result_id": "result-a", "last_reason": None,
    }
    code, out, err, log, lines = _run(home, http)
    assert code == 0 and http.posts == []
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    finals = [e for e in reducer.events if e.event_type == EventType.FINAL]
    assert len(finals) == 1
    assert "task_id=task-a" in finals[0].evidence_ref
    assert "accepted_result_id=result-a" in finals[0].evidence_ref
    assert "attempt=1" in finals[0].evidence_ref
    assert "spec_fingerprint=fp" in finals[0].evidence_ref
    assert f"source_sha={SHA}" in finals[0].evidence_ref
    before = (home / "coordination_ledger.jsonl").read_text(encoding="utf-8")
    assert _run(home, http)[0] == 0
    assert http.posts == []
    assert (home / "coordination_ledger.jsonl").read_text(encoding="utf-8") == before


def test_bad_config_exits_2_without_posting(tmp_path):
    http = FakeHTTP()
    home = _home(tmp_path, None)
    _seed(home, [_ready("A", "a-assign")])
    assert _run(home, http)[0] == 2 and http.posts == []

    home = _home(tmp_path / "bad", {"A": {"adapter": "Nope", "params": [], "effect_class": "maybe"}})
    _seed(home, [_ready("A", "a-assign")])
    assert _run(home, http)[0] == 2 and http.posts == []

    home = _home(tmp_path / "agent", {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    out, err = [], []
    code = main(
        ["--home", str(home), "--agent-id", "COURIER_V1_BRIDGE", "--host-id", HOST,
         "--controller", "http://127.0.0.1:9"],
        http=http, stdout=out.append, stderr=err.append,
    )
    assert code == 2 and http.posts == []

    home = _home(tmp_path / "url", {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    code = main(
        ["--home", str(home), "--agent-id", AGENT, "--host-id", HOST,
         "--controller", "http://10.1.2.3:9"],
        http=http, stdout=out.append, stderr=err.append,
    )
    assert code == 2 and http.posts == []

    home = _home(tmp_path / "declared", {"A": _spec(source_sha="nope")})
    _seed(home, [_ready("A", "a-assign")])
    assert _run(home, http)[0] == 2 and http.posts == []

    home = _home(tmp_path / "nosha", {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    import scripts.ledger_v1_bridge as bridge
    previous = bridge._git_head
    bridge._git_head = lambda: ""
    try:
        assert _run(home, http)[0] == 2 and http.posts == []
    finally:
        bridge._git_head = previous


def test_goal_fields_round_trip_into_evidence_and_replay_is_noop(tmp_path):
    goal_id = "g" * 128
    goal_fp = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    http = FakeHTTP()
    home = _home(tmp_path, {"A": _spec(goal_id=goal_id, goal_fingerprint=goal_fp)})
    _seed(home, [_ready("A", "a-assign")])
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err
    assert len(http.posts) == 1
    posted = http.posts[0]
    assert posted["idempotency_key"].startswith("ledger:claim-")
    assert "goal_id" not in posted["idempotency_key"]
    assert "goal_id" not in posted
    assert posted["params"]["unit"] == "a"
    assert posted["params"]["goal_id"] == goal_id
    assert posted["params"]["goal_fingerprint"] == goal_fp
    task_id = "task-" + hashlib.sha256(posted["idempotency_key"].encode()).hexdigest()[:32]
    http.views[task_id]["status"] = "COMPLETE"
    http.views[task_id]["accepted_result_id"] = "result-goal"
    http.views[task_id]["attempt"] = 1
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err
    assert len(http.posts) == 1
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    finals = [event for event in reducer.events if event.event_type == EventType.FINAL]
    assert len(finals) == 1
    assert f"goal_id={goal_id}" in finals[0].evidence_ref
    assert f"goal_fingerprint={goal_fp}" in finals[0].evidence_ref
    assert finals[0].payload_hash == hashlib.sha256(finals[0].evidence_ref.encode("utf-8")).hexdigest()
    before = (home / "coordination_ledger.jsonl").read_text(encoding="utf-8")
    assert _run(home, http)[0] == 0
    assert len(http.posts) == 1
    assert (home / "coordination_ledger.jsonl").read_text(encoding="utf-8") == before


def test_half_or_invalid_goal_is_blocked_and_not_posted(tmp_path):
    cases = [
        {"goal_id": "only-id"},
        {"goal_fingerprint": "b" * 64},
        {"goal_id": "ok-id", "goal_fingerprint": "bad fp"},
        {"goal_id": "a" * 129, "goal_fingerprint": "fp"},
        {"goal_id": "", "goal_fingerprint": "fp"},
        {"goal_id": "goal\nid", "goal_fingerprint": "fp"},
        {"goal_id": 12, "goal_fingerprint": "fp"},
        {"goal_id": "ok-id", "goal_fingerprint": "fp/extra"},
    ]
    for index, extra in enumerate(cases):
        http = FakeHTTP()
        home = _home(tmp_path / str(index), {"A": _spec(**extra)})
        _seed(home, [_ready("A", "a-assign")])
        code, out, err, log, lines = _run(home, http)
        assert code == 0, (extra, err, out)
        assert http.posts == [], extra
        reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
        mission = reducer.get_mission("A")
        assert mission["status"] == MissionStatus.BLOCKED, extra
        assert mission["blocker"]
        assert "goal" in mission["blocker"]
        blocked = [event for event in reducer.events if event.event_type == EventType.BLOCKED]
        assert len(blocked) == 1, extra
        assert blocked[0].payload_hash == hashlib.sha256(blocked[0].evidence_ref.encode("utf-8")).hexdigest()
        assert not any(event.event_type == EventType.FINAL for event in reducer.events)
        assert not any(event.event_type == EventType.STARTED for event in reducer.events)
        before = (home / "coordination_ledger.jsonl").read_text(encoding="utf-8")
        assert _run(home, http)[0] == 0
        assert http.posts == []
        assert (home / "coordination_ledger.jsonl").read_text(encoding="utf-8") == before


def _state(home):
    return json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))["missions"]


def test_mission_status_posted_then_final_done_and_replay_is_stable(tmp_path):
    http = FakeHTTP()
    home = _home(tmp_path, {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    assert _run(home, http)[0] == 0
    posted = _state(home)["A"]
    assert posted["status"] == "POSTED"
    assert posted["reason"] is None
    assert posted["accepted_result_id"] is None
    assert posted["updated_at"].endswith("Z") and "T" in posted["updated_at"]
    task_id = posted["task_id"]
    http.views[task_id]["status"] = "COMPLETE"
    http.views[task_id]["accepted_result_id"] = "result-a"
    http.views[task_id]["attempt"] = 1
    assert _run(home, http)[0] == 0
    done = _state(home)["A"]
    assert done["status"] == "FINAL_DONE"
    assert done["reason"] is None
    assert done["accepted_result_id"] == "result-a"
    assert done["updated_at"] >= posted["updated_at"]
    frozen = (home / "ledger_bridge_state.json").read_text(encoding="utf-8")
    assert _run(home, http)[0] == 0
    assert (home / "ledger_bridge_state.json").read_text(encoding="utf-8") == frozen
    assert _state(home)["A"]["updated_at"] == done["updated_at"]


def test_mission_status_blocked_and_error_never_final_done(tmp_path):
    http = FakeHTTP()
    home = _home(tmp_path / "blocked", {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    (home / "ledger_bridge_state.json").write_text(json.dumps({"missions": {"A": _mapped()}}), encoding="utf-8")
    http.views["task-a"] = {
        "task_id": "task-a", "status": "BLOCKED", "attempt": 2,
        "accepted_result_id": None, "last_reason": "needs a person",
    }
    assert _run(home, http)[0] == 0 and http.posts == []
    blocked = _state(home)["A"]
    assert blocked["status"] == "BLOCKED"
    assert blocked["reason"] == "CONTROLLER_BLOCKED"
    assert blocked["status"] != "FINAL_DONE"
    assert "/" not in blocked["reason"] and "\\" not in blocked["reason"]
    frozen = (home / "ledger_bridge_state.json").read_text(encoding="utf-8")
    assert _run(home, http)[0] == 0
    assert (home / "ledger_bridge_state.json").read_text(encoding="utf-8") == frozen

    for controller_status, code in (("FAILED", "FAILED"), ("CANCELLED", "CANCELLED")):
        http = FakeHTTP()
        home = _home(tmp_path / controller_status, {"A": _spec()})
        _seed(home, [_ready("A", "a-assign")])
        (home / "ledger_bridge_state.json").write_text(json.dumps({"missions": {"A": _mapped()}}), encoding="utf-8")
        http.views["task-a"] = {
            "task_id": "task-a", "status": controller_status, "attempt": 1,
            "accepted_result_id": None, "last_reason": "boom",
        }
        assert _run(home, http)[0] == 0 and http.posts == []
        record = _state(home)["A"]
        assert record["status"] == "ERROR"
        assert record["reason"] == code
        assert record["status"] != "FINAL_DONE"
        frozen = (home / "ledger_bridge_state.json").read_text(encoding="utf-8")
        assert _run(home, http)[0] == 0
        assert (home / "ledger_bridge_state.json").read_text(encoding="utf-8") == frozen

    http = FakeHTTP()
    home = _home(tmp_path / "goal", {"A": _spec(goal_id="only-id")})
    _seed(home, [_ready("A", "a-assign")])
    (home / "ledger_bridge_state.json").write_text(json.dumps({"missions": {"A": _mapped()}}), encoding="utf-8")
    http.views["task-a"] = {
        "task_id": "task-a", "status": "COMPLETE", "attempt": 1,
        "accepted_result_id": "result-a", "last_reason": None,
    }
    assert _run(home, http)[0] == 0 and http.posts == []
    goal = _state(home)["A"]
    assert goal["status"] == "BLOCKED"
    assert goal["reason"] == "GOAL_PAIR"
    assert goal["status"] != "FINAL_DONE"
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    assert not any(event.event_type == EventType.FINAL for event in reducer.events)
    frozen = (home / "ledger_bridge_state.json").read_text(encoding="utf-8")
    assert _run(home, http)[0] == 0
    assert (home / "ledger_bridge_state.json").read_text(encoding="utf-8") == frozen


def test_legacy_state_loads_derived_status_without_rewrite(tmp_path):
    posted_home = _home(tmp_path / "posted", {"A": _spec()})
    legacy = {"missions": {"A": _mapped()}}
    posted_path = posted_home / "ledger_bridge_state.json"
    posted_path.write_text(json.dumps(legacy), encoding="utf-8")
    loaded = _load_state(posted_path)
    assert loaded["missions"]["A"]["status"] == "POSTED"
    assert loaded["missions"]["A"]["reason"] is None
    assert "status" not in json.loads(posted_path.read_text(encoding="utf-8"))["missions"]["A"]

    done = _mapped()
    done["accepted_result_id"] = "result-a"
    done_path = _home(tmp_path / "done", {"A": _spec()}) / "ledger_bridge_state.json"
    done_path.write_text(json.dumps({"missions": {"A": done}}), encoding="utf-8")
    loaded_done = _load_state(done_path)
    assert loaded_done["missions"]["A"]["status"] == "FINAL_DONE"
    assert loaded_done["missions"]["A"]["reason"] is None

    waiting = _mapped()
    waiting["posted"] = False
    waiting["accepted_result_id"] = None
    waiting_path = _home(tmp_path / "wait", {"A": _spec()}) / "ledger_bridge_state.json"
    waiting_path.write_text(json.dumps({"missions": {"A": waiting}}), encoding="utf-8")
    loaded_wait = _load_state(waiting_path)
    assert loaded_wait["missions"]["A"].get("status") not in ("FINAL_DONE", "BLOCKED", "ERROR")

    _seed(posted_home, [_ready("A", "a-assign")])
    http = FakeHTTP()
    http.views["task-a"] = {
        "task_id": "task-a", "status": "QUEUED", "attempt": 0,
        "accepted_result_id": None, "last_reason": None,
    }
    frozen = posted_path.read_text(encoding="utf-8")
    assert _run(posted_home, http)[0] == 0
    assert posted_path.read_text(encoding="utf-8") == frozen


def test_token_never_appears_in_stdout_stderr_or_log(tmp_path):
    http = FakeHTTP()
    home = _home(tmp_path, {"A": _spec()})
    _seed(home, [_ready("A", "a-assign")])
    code, out, err, log, lines = _run(home, http)
    assert code == 0 and len(http.posts) == 1
    blob = out + err + log + (home / "ledger_bridge_state.json").read_text(encoding="utf-8")
    blob += (home / "coordination_ledger.jsonl").read_text(encoding="utf-8")
    assert TOKEN not in blob
    assert "Bearer" not in out + err + log
