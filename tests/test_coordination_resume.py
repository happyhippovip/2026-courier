"""Cross-session continuation acceptance for the coordination ledger.

WORKER A writes durable PARTIAL checkpoints and its process disappears.  A FRESH
worker process (no shared memory, no copied chat) reconstructs the checkpoint
from shared truth only and safely claims/resumes it with zero duplicate writers.
"""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.coordination_ledger import (
    AgentID, CoordinationEvent, CoordinationReducer, EventType, HostID, MissionStatus,
)
from scripts.coordination_resume import (
    CLAIMED, CONFLICT, NOT_RESUMABLE, REASSIGN, RESUME, UNKNOWN_AUTHORITY,
    claim_mission, discover_resumable, reduce_store,
)
from scripts.github_coordination import (
    FileCoordinationStore, GitHubCoordinationAdapter, extract_events_from_body, render_event_body,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

WORKER_A_SCRIPT = r"""
import os, sys
sys.path.insert(0, sys.argv[2])
from scripts.coordination_ledger import AgentID, CoordinationEvent, EventType, HostID, MissionStatus
from scripts.github_coordination import FileCoordinationStore
store = FileCoordinationStore(sys.argv[1])
def ev(eid, etype, ts, **kw):
    return CoordinationEvent(event_id=eid, mission_id="WK-42", agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE, event_type=etype, status=MissionStatus.WORKING, depends_on=[],
        head=kw.get("head"), evidence_ref=kw.get("evidence", "ev://start"), created_at=ts,
        payload_hash=eid, branch="lane/L2-wk-42", pr="153", test_evidence=kw.get("tests"),
        next_action=kw.get("next"))
store.write_event(ev("a-assign", EventType.ASSIGNED, "2026-10-07T12:00:00Z", head="aaa111"))
store.write_event(ev("a-partial", EventType.PARTIAL, "2026-10-07T12:30:00Z", head="bbb222",
    evidence="ev://partial-1", tests="tests/test_x.py::PASS", next="implement claim verification"))
os._exit(0)  # Worker/session disappears abruptly: no cleanup, no handoff.
"""


def _event(eid, mid, etype, status, ts, agent=AgentID.GOOGLE_WINDOWS, host=HostID.WINDOWS_REMOTE,
           deps=None, owner=None, **kw):
    return CoordinationEvent(
        event_id=eid, mission_id=mid, agent_id=agent, host_id=host, event_type=etype, status=status,
        depends_on=deps or [], head=kw.get("head", "sha"), evidence_ref=kw.get("evidence", "ref"),
        created_at=ts, payload_hash="h", branch=kw.get("branch"), next_action=kw.get("next"),
        ownership=owner,
    )


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "scripts.coordination_status", *args],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60,
    )


def test_fresh_process_reconstructs_and_resumes(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    a = subprocess.run([sys.executable, "-c", WORKER_A_SCRIPT, str(ledger), str(REPO_ROOT)],
                       capture_output=True, text=True, timeout=60)
    assert a.returncode == 0, a.stderr

    # Fresh worker B session: separate process, only the shared ledger path.
    disc = _run_cli("--events-file", str(ledger), "--agent", "GOOGLE_WINDOWS", "--discover")
    assert disc.returncode == 0, disc.stderr
    found = json.loads(disc.stdout)
    assert len(found) == 1
    cp = found[0]
    assert cp["mission_id"] == "WK-42" and cp["mode"] == RESUME
    assert cp["branch"] == "lane/L2-wk-42" and cp["head"] == "bbb222" and cp["pr"] == "153"
    assert cp["evidence_ref"] == "ev://partial-1"
    assert cp["test_evidence"] == "tests/test_x.py::PASS"
    assert cp["next_action"] == "implement claim verification"

    claim = _run_cli("--events-file", str(ledger), "--agent", "GOOGLE_WINDOWS",
                     "--host", "WINDOWS_REMOTE", "--claim", "WK-42")
    assert claim.returncode == 0, claim.stdout + claim.stderr
    assert json.loads(claim.stdout)["outcome"] == CLAIMED

    # Duplicate claim (retry / replay): no new effect, still exactly one writer event.
    again = _run_cli("--events-file", str(ledger), "--agent", "GOOGLE_WINDOWS",
                     "--host", "WINDOWS_REMOTE", "--claim", "WK-42")
    assert json.loads(again.stdout)["outcome"] == CLAIMED
    lines = [l for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3

    # A different worker cannot steal the live mission.
    steal = _run_cli("--events-file", str(ledger), "--agent", "GOOGLE_MAC",
                     "--host", "MAC_LOCAL", "--claim", "WK-42")
    assert steal.returncode == 2
    assert json.loads(steal.stdout)["outcome"] == CONFLICT
    assert reduce_store(FileCoordinationStore(ledger)).get_mission("WK-42")["ownership"] == "GOOGLE_WINDOWS"


def test_stale_checkpoint_does_not_regress_resume_point(tmp_path):
    store = FileCoordinationStore(tmp_path / "l.jsonl")
    store.write_event(_event("1", "m", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z"))
    store.write_event(_event("2", "m", EventType.PARTIAL, MissionStatus.WORKING, "2026-10-07T13:00:00Z",
                             head="new", next="newer step"))
    store.write_event(_event("3", "m", EventType.PARTIAL, MissionStatus.WORKING, "2026-10-07T12:30:00Z",
                             head="old", next="older step"))
    [cp] = discover_resumable(reduce_store(store), AgentID.GOOGLE_WINDOWS)
    assert cp.head == "new" and cp.next_action == "newer step" and cp.latest_event_id == "2"


def test_duplicate_events_in_shared_truth_have_no_duplicate_effect(tmp_path):
    store = FileCoordinationStore(tmp_path / "l.jsonl")
    e = _event("1", "m", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z")
    store.write_event(e)
    store.write_event(e)
    reducer = reduce_store(store)
    assert len(reducer.events) == 1
    assert len(discover_resumable(reducer, AgentID.GOOGLE_WINDOWS)) == 1


def test_assigned_cannot_take_over_live_owned_mission():
    r = CoordinationReducer()
    r.apply(_event("1", "m", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z"))
    took = r.apply(_event("2", "m", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:05:00Z",
                          agent=AgentID.GOOGLE_MAC, host=HostID.MAC_LOCAL))
    assert took is False
    assert r.get_mission("m")["ownership"] == "GOOGLE_WINDOWS"


def test_racing_reassignment_yields_exactly_one_writer(tmp_path):
    store = FileCoordinationStore(tmp_path / "l.jsonl")
    store.write_event(_event("1", "m", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z",
                             agent=AgentID.CODEX_MAC, host=HostID.MAC_LOCAL))
    store.write_event(_event("2", "m", EventType.ERROR, MissionStatus.ERROR, "2026-10-07T12:10:00Z",
                             agent=AgentID.CODEX_MAC, host=HostID.MAC_LOCAL))

    # Both workers observed the same ERROR snapshot before either write lands.
    snapshot = store.read_events()

    class SnapshotThenLive:
        def __init__(self):
            self.first = True
        def read_events(self):
            if self.first:
                self.first = False
                return list(snapshot)
            return store.read_events()
        def write_event(self, event):
            return store.write_event(event)

    win = claim_mission(SnapshotThenLive(), AgentID.GOOGLE_WINDOWS, HostID.WINDOWS_REMOTE, "m")
    mac = claim_mission(SnapshotThenLive(), AgentID.GOOGLE_MAC, HostID.MAC_LOCAL, "m")
    assert sorted([win.outcome, mac.outcome]) == [CLAIMED, CONFLICT]
    assert reduce_store(store).get_mission("m")["ownership"] == "GOOGLE_WINDOWS"


def test_error_is_offered_for_reassignment_and_claimed(tmp_path):
    store = FileCoordinationStore(tmp_path / "l.jsonl")
    store.write_event(_event("1", "m", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z",
                             branch="lane/x"))
    store.write_event(_event("2", "m", EventType.ERROR, MissionStatus.ERROR, "2026-10-07T12:10:00Z"))
    [cp] = discover_resumable(reduce_store(store), AgentID.GOOGLE_MAC)
    assert cp.mode == REASSIGN and cp.branch == "lane/x"
    res = claim_mission(store, AgentID.GOOGLE_MAC, HostID.MAC_LOCAL, "m")
    assert res.outcome == CLAIMED
    m = reduce_store(store).get_mission("m")
    assert m["ownership"] == "GOOGLE_MAC" and m["status"] == MissionStatus.WORKING


def test_dependency_unlock_and_blocked_unrelated(tmp_path):
    store = FileCoordinationStore(tmp_path / "l.jsonl")
    store.write_event(_event("1", "B", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z",
                             deps=["A"]))
    store.write_event(_event("2", "X", EventType.BLOCKED, MissionStatus.BLOCKED, "2026-10-07T12:00:00Z"))
    store.write_event(_event("3", "U", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z"))
    ids = {c.mission_id for c in discover_resumable(reduce_store(store), AgentID.GOOGLE_WINDOWS)}
    assert ids == {"U"}  # B locked behind A; blocked X never offered; unrelated U not frozen.
    assert claim_mission(store, AgentID.GOOGLE_WINDOWS, HostID.WINDOWS_REMOTE, "B").outcome == NOT_RESUMABLE

    store.write_event(_event("4", "A", EventType.FINAL, MissionStatus.DONE, "2026-10-07T12:20:00Z",
                             agent=AgentID.CODEX_MAC, host=HostID.MAC_LOCAL))
    ids = {c.mission_id for c in discover_resumable(reduce_store(store), AgentID.GOOGLE_WINDOWS)}
    assert ids == {"B", "U"}


def test_unknown_authority_fails_closed(tmp_path):
    store = FileCoordinationStore(tmp_path / "l.jsonl")
    store.write_event(_event("1", "m", EventType.ERROR, MissionStatus.ERROR, "2026-10-07T12:00:00Z"))
    assert claim_mission(store, AgentID.UNKNOWN, HostID.WINDOWS_REMOTE, "m").outcome == UNKNOWN_AUTHORITY
    assert claim_mission(store, AgentID.GOOGLE_MAC, HostID.UNKNOWN, "m").outcome == UNKNOWN_AUTHORITY
    assert discover_resumable(reduce_store(store), AgentID.UNKNOWN) == []

    # Unlisted agent strings from shared truth collapse to UNKNOWN and never mutate state.
    path = tmp_path / "forged.jsonl"
    forged = _event("f", "z", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z").to_dict()
    forged["agent_id"] = "EVIL_BOT"
    path.write_text(json.dumps(forged) + "\n", encoding="utf-8")
    assert reduce_store(FileCoordinationStore(path)).get_mission("z") is None

    cli = _run_cli("--events-file", str(store.path), "--agent", "EVIL_BOT", "--host", "MAC_LOCAL", "--claim", "m")
    assert cli.returncode == 2 and json.loads(cli.stdout)["outcome"] == UNKNOWN_AUTHORITY


def test_naive_or_garbage_timestamp_is_rejected():
    r = CoordinationReducer()
    assert r.apply(_event("1", "m", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00")) is False
    assert r.apply(_event("2", "m", EventType.ASSIGNED, MissionStatus.WORKING, "yesterday")) is False
    assert r.get_mission("m") is None


def test_github_written_event_round_trips_through_reader():
    e = _event("1", "m", EventType.PARTIAL, MissionStatus.WORKING, "2026-10-07T12:00:00Z", branch="b")
    [back] = extract_events_from_body(render_event_body(e))
    assert back == e and back.agent_id is AgentID.GOOGLE_WINDOWS


@patch("requests.get")
def test_github_reader_paginates_and_fails_on_partial_read(mock_get):
    e = _event("1", "m", EventType.ASSIGNED, MissionStatus.WORKING, "2026-10-07T12:00:00Z")
    full = [{"body": "noise"}] * 99 + [{"body": render_event_body(e)}]
    page2 = MagicMock(status_code=200)
    page2.json.return_value = [{"body": render_event_body(
        _event("2", "m", EventType.PARTIAL, MissionStatus.WORKING, "2026-10-07T12:05:00Z"))}]
    page1 = MagicMock(status_code=200)
    page1.json.return_value = full
    mock_get.side_effect = [page1, page2]
    events = GitHubCoordinationAdapter("o/r", 6, "t").read_events()
    assert [x.event_id for x in events] == ["1", "2"]

    bad = MagicMock(status_code=502)
    mock_get.side_effect = [page1, bad]
    try:
        GitHubCoordinationAdapter("o/r", 6, "t").read_events()
    except RuntimeError:
        pass
    else:
        raise AssertionError("partial ledger read must not be treated as complete truth")
