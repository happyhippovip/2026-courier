"""Synthetic GOOGLE_WINDOWS → MUSE_MAC handoff. Not a live provider run.

SYNTHETIC_VERIFIED only. REAL_PROVIDER stays NOT_TESTED. Cost stays 0 EUR.
"""

from __future__ import annotations

import json

from scripts.coordination_ledger import AgentID, EventType, HostID, MissionStatus
from scripts.coordination_resume import CLAIMED, CONFLICT, claim_mission, reduce_store
from scripts.github_coordination import FileCoordinationStore
from scripts.ledger_v1_bridge import main
from tests.test_ledger_v1_bridge import (
    AGENT,
    HOST,
    TOKEN,
    FakeHTTP,
    _event,
    _home,
    _ready,
    _seed,
    _spec,
)


MAC = AgentID.MUSE_MAC.value
MAC_HOST = HostID.MAC_LOCAL.value


def _mac_ready(mid, eid, ts, deps=None):
    from scripts.coordination_ledger import CoordinationEvent

    return CoordinationEvent(
        event_id=eid,
        mission_id=mid,
        agent_id=AgentID.MUSE_MAC,
        host_id=HostID.MAC_LOCAL,
        event_type=EventType.ASSIGNED,
        status=MissionStatus.WORKING,
        depends_on=deps or [],
        head="sha",
        evidence_ref="ref",
        created_at=ts,
        payload_hash="b" * 64,
        ownership=MAC,
    )


def _mac_spec():
    return _spec(
        params={"unit": "b"},
        agent_id=MAC,
        host_id=MAC_HOST,
        estimated_cost_eur=0.0,
    )


def _run(home, http, agent, host):
    out, err = [], []
    code = main(
        [
            "--home", str(home),
            "--agent-id", agent,
            "--host-id", host,
            "--controller", "http://127.0.0.1:9",
        ],
        http=http,
        stdout=out.append,
        stderr=err.append,
    )
    return code, "".join(out), "".join(err)


def _pair(tmp_path):
    http = FakeHTTP()
    home = _home(tmp_path, {"A": _spec(), "B": _mac_spec()})
    _seed(home, [
        _ready("A", "a-assign", "2026-10-23T08:00:00Z"),
        _mac_ready("B", "b-assign", "2026-10-23T08:00:01Z", deps=["A"]),
    ])
    return http, home


def _finish_a(http):
    task_id = next(iter(http.views))
    http.views[task_id].update({
        "status": "COMPLETE",
        "attempt": 1,
        "accepted_result_id": "result-a",
        "resolution": "verified",
    })
    return task_id


def test_windows_does_not_post_mac_mission_before_a_is_verified(tmp_path):
    http, home = _pair(tmp_path)
    code, out, err = _run(home, http, AGENT, HOST)
    assert code == 0, err
    assert len(http.posts) == 1
    assert "B" not in out

    http.views[next(iter(http.views))].update({
        "status": "COMPLETE",
        "attempt": 1,
        "accepted_result_id": "result-a",
    })
    code, out, err = _run(home, http, AGENT, HOST)
    assert "final" not in out
    assert len(http.posts) == 1
    mac_code, mac_out, mac_err = _run(home, http, MAC, MAC_HOST)
    assert mac_code == 0, mac_err
    assert len(http.posts) == 1
    assert "queued" not in mac_out


def test_mac_receives_the_next_mission_after_windows_verifies(tmp_path):
    http, home = _pair(tmp_path)
    assert _run(home, http, AGENT, HOST)[0] == 0
    _finish_a(http)
    code, out, err = _run(home, http, AGENT, HOST)
    assert code == 0, err
    assert '"outcome":"final"' in out
    assert len(http.posts) == 1

    store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    stolen = claim_mission(store, AgentID.GOOGLE_WINDOWS, HostID.WINDOWS_REMOTE, "B")
    assert stolen.outcome == CONFLICT

    mac_code, mac_out, mac_err = _run(home, http, MAC, MAC_HOST)
    assert mac_code == 0, mac_err
    assert len(http.posts) == 2
    assert http.posts[1]["params"]["unit"] == "b"
    assert '"proof":"SYNTHETIC"' in mac_out
    assert '"owner":"MUSE_MAC"' in mac_out
    reducer = reduce_store(store)
    mission_b = reducer.get_mission("B")
    assert mission_b["ownership"] == MAC
    assert mission_b["status"] == MissionStatus.WORKING

    again = claim_mission(store, AgentID.MUSE_MAC, HostID.MAC_LOCAL, "B")
    assert again.outcome == CLAIMED
    replay_code, replay_out, replay_err = _run(home, http, MAC, MAC_HOST)
    assert replay_code == 0, replay_err
    assert len(http.posts) == 2
    assert replay_out.count('"outcome":"queued"') == 0


def test_offline_mac_blocks_instead_of_completing(tmp_path):
    http, home = _pair(tmp_path)
    assert _run(home, http, AGENT, HOST)[0] == 0
    _finish_a(http)
    assert _run(home, http, AGENT, HOST)[0] == 0
    marker = home / "hosts"
    marker.mkdir()
    (marker / "MAC_LOCAL.offline").write_text("synthetic-offline\n", encoding="utf-8")
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 2
    assert "target_host_unavailable" in out
    assert '"proof":"SYNTHETIC"' in out
    assert len(http.posts) == 1
    mission_b = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl")).get_mission("B")
    assert mission_b["status"] == MissionStatus.BLOCKED
    assert mission_b["status"] != MissionStatus.DONE


def test_missing_handoff_cost_blocks(tmp_path):
    http = FakeHTTP()
    spec_b = _mac_spec()
    del spec_b["estimated_cost_eur"]
    home = _home(tmp_path, {"A": _spec(), "B": spec_b})
    _seed(home, [
        _ready("A", "a-assign", "2026-10-23T08:00:00Z"),
        _mac_ready("B", "b-assign", "2026-10-23T08:00:01Z", deps=["A"]),
    ])
    assert _run(home, http, AGENT, HOST)[0] == 0
    _finish_a(http)
    assert _run(home, http, AGENT, HOST)[0] == 0
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 2
    assert "UNKNOWN_COST" in out
    assert len(http.posts) == 1


def test_sender_restart_does_not_post_the_mac_mission_twice(tmp_path):
    http, home = _pair(tmp_path)
    assert _run(home, http, AGENT, HOST)[0] == 0
    assert _run(home, http, AGENT, HOST)[0] == 0
    assert len(http.posts) == 1
    assert TOKEN not in json.dumps(http.posts)


def _only_b(tmp_path, spec):
    http = FakeHTTP()
    home = _home(tmp_path, {"B": spec})
    _seed(home, [_mac_ready("B", "b-assign", "2026-10-23T08:00:01Z")])
    return http, home


def test_wrong_actor_is_not_posted(tmp_path):
    spec = _mac_spec()
    spec["agent_id"] = AGENT
    http, home = _only_b(tmp_path, spec)
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 2, err
    assert "wrong_agent" in out
    assert http.posts == []


def test_wrong_host_is_not_posted(tmp_path):
    spec = _mac_spec()
    spec["host_id"] = HOST
    http, home = _only_b(tmp_path, spec)
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 2, err
    assert "wrong_host" in out
    assert http.posts == []


def test_string_zero_cost_is_not_posted(tmp_path):
    spec = _mac_spec()
    spec["estimated_cost_eur"] = "0"
    http, home = _only_b(tmp_path, spec)
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 2, err
    assert "malformed" in err
    assert '"outcome":"queued"' not in out
    assert http.posts == []


def test_host_id_without_agent_still_blocks_unknown_cost(tmp_path):
    http = FakeHTTP()
    spec_b = _spec(params={"unit": "b"}, host_id=MAC_HOST)
    home = _home(tmp_path, {"A": _spec(), "B": spec_b})
    _seed(home, [
        _ready("A", "a-assign", "2026-10-23T08:00:00Z"),
        _mac_ready("B", "b-assign", "2026-10-23T08:00:01Z", deps=["A"]),
    ])
    assert _run(home, http, AGENT, HOST)[0] == 0
    _finish_a(http)
    assert _run(home, http, AGENT, HOST)[0] == 0
    code, out, err = _run(home, http, MAC, MAC_HOST)
    assert code == 2, err
    assert "UNKNOWN_COST" in out
    assert len(http.posts) == 1
