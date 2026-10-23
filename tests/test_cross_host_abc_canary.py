"""Synthetic A→B→C canary: GOOGLE_WINDOWS verifies A, MUSE_MAC takes B, then C.

SYNTHETIC_VERIFIED only. REAL_PROVIDER stays NOT_TESTED. Cost stays 0 EUR.
The mission chip is a separate hub surface and is not written by this bridge.
"""

from __future__ import annotations

import hashlib
import json

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
