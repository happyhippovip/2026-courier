"""Negative proofs for the six A→B gaps. Each test fails on the unfixed code."""

from __future__ import annotations

import json
import sys
from unittest import mock

import pytest

from courier_runtime.lease import LeaseStore, StaleLease
from scripts.coordination_ledger import (
    AgentID,
    CoordinationEvent,
    EventType,
    HostID,
    MissionStatus,
)
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore
from scripts.ledger_v1_bridge import _write_new
from scripts.resource_policy import CostGate, TaskLeaseManager
from scripts.run_autonomous_loop import AutonomousLevel6Loop, WorkflowLockedError


def _event(event_id, mission_id, agent, owner, created_at, event_type=EventType.ASSIGNED):
    return CoordinationEvent(
        event_id=event_id,
        mission_id=mission_id,
        agent_id=agent,
        host_id=HostID.WINDOWS_REMOTE if agent == AgentID.GOOGLE_WINDOWS else HostID.MAC_LOCAL,
        event_type=event_type,
        status=MissionStatus.WORKING if event_type != EventType.FINAL else MissionStatus.DONE,
        depends_on=[],
        head="abc",
        evidence_ref="synthetic",
        created_at=created_at,
        payload_hash="a" * 64,
        ownership=owner,
    )


def test_ledger_validate_before_write_rejects_foreign_owner(tmp_path):
    """A conflicting writer must not be appended. Validation happens before the write."""
    path = tmp_path / "coordination_ledger.jsonl"
    store = FileCoordinationStore(path)
    reducer = reduce_store(store)
    first = _event(
        "e-a", "mission-ab", AgentID.GOOGLE_WINDOWS, "GOOGLE_WINDOWS", "2026-10-22T08:00:00Z",
    )
    assert _write_new(store, reducer, first) is True
    foreign = _event(
        "e-b", "mission-ab", AgentID.MUSE_MAC, "MUSE_MAC", "2026-10-22T08:05:00Z",
        event_type=EventType.PARTIAL,
    )
    wrote = _write_new(store, reducer, foreign)
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert wrote is False
    assert len(lines) == 1
    assert json.loads(lines[0])["event_id"] == "e-a"


def test_lease_holder_scope_and_token_are_fenced(tmp_path):
    """Token and holder are both required. A child token cannot write the parent.
    The same integer token must not be issued to two scopes."""
    store = LeaseStore(str(tmp_path / "lease.db"))
    problems = []
    try:
        child = store.acquire("repo://proj/child", "agent-a", "wk-child", ttl_s=30)
        try:
            store.check_write("repo://proj", child.token)
            problems.append("child token authorized a parent write")
        except StaleLease:
            pass
        try:
            store.check_write("repo://proj", child.token, "agent-a")
        except StaleLease:
            pass
        except TypeError:
            problems.append("check_write does not accept a holder")
        else:
            problems.append("child holder token authorized a parent write")

        other = store.acquire("repo://other", "agent-a", "wk-child", ttl_s=30)
        if child.token == other.token:
            problems.append(f"cross-scope token collision token={child.token}")
        try:
            store.check_write(other.scope, other.token, "agent-b")
        except StaleLease:
            pass
        except TypeError:
            problems.append("check_write does not check holder")
        else:
            problems.append("wrong holder was accepted for a live token")
        try:
            store.check_write(child.scope, True, "agent-a")
        except StaleLease:
            pass
        except TypeError:
            problems.append("bool token was not rejected as a non-token")
        else:
            problems.append("bool token was accepted")
    finally:
        store.close()
    if problems:
        raise AssertionError(" | ".join(problems))


def test_fencing_token_is_really_checked(tmp_path, monkeypatch):
    """A refused fence blocks the task lease and the workflow lock."""
    def refuse(self, scope, token, holder=None):
        raise StaleLease("fence refused")

    monkeypatch.setattr(LeaseStore, "check_write", refuse)
    problems = []
    manager = TaskLeaseManager(tmp_path / "repo-fence")
    ok, _reason, data = manager.acquire_lease("job-fence", "hash-fence", "runner-a", 30)
    if ok is True or "fencing_token" in data:
        problems.append("task lease succeeded without a checked fencing token")
    loop = AutonomousLevel6Loop(repo_dir=tmp_path / "repo-loop")
    try:
        loop.acquire_workflow_lock("wf-fence")
        problems.append("workflow lock succeeded without a checked fencing token")
    except WorkflowLockedError:
        pass
    if problems:
        raise AssertionError(" | ".join(problems))


def test_authority_exception_fails_closed(tmp_path, monkeypatch):
    """except Exception must BLOCK. It must not report the lease or lock as held."""
    def boom(self, *args, **kwargs):
        raise RuntimeError("authority unavailable")

    monkeypatch.setattr(LeaseStore, "acquire", boom)
    problems = []
    manager = TaskLeaseManager(tmp_path / "repo-boom")
    ok, _reason, _data = manager.acquire_lease("job-boom", "hash-boom", "runner-a", 30)
    if ok is not False:
        problems.append("task lease returned success after an authority exception")
    lease_file = manager._get_lease_path("job-boom")
    if lease_file.exists():
        problems.append("task lease file remained after an authority exception")
    loop = AutonomousLevel6Loop(repo_dir=tmp_path / "repo-loop-boom")
    try:
        loop.acquire_workflow_lock("wf-boom")
        problems.append("workflow lock swallowed an authority exception")
    except WorkflowLockedError:
        pass
    lock_file = tmp_path / "repo-loop-boom" / "events" / "locks" / "wf-boom.lock"
    if lock_file.exists():
        problems.append("workflow lock file remained after an authority exception")
    if problems:
        raise AssertionError(" | ".join(problems))


def test_unknown_cost_is_blocked_not_zero(tmp_path, monkeypatch):
    """A missing cost must not be coerced to 0.0 and must not spawn a provider."""
    from scripts import gemini_worker_adapter

    task_file = tmp_path / "missing-cost.json"
    task_file.write_text(json.dumps({"task_id": "gemini-missing", "instruction": "do it"}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with mock.patch("subprocess.Popen") as popen:
        result = gemini_worker_adapter.run_worker(str(task_file))
    popen.assert_not_called()
    assert isinstance(result, dict)
    assert result.get("blocked") is True
    assert "UNKNOWN_COST" in str(result.get("reason"))
    direct = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=None)
    assert direct["allowed"] is False
    assert direct["reason"] == "UNKNOWN_COST"
    explicit = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0)
    assert explicit["allowed"] is True


def test_mailbox_dedupes_same_task_id(tmp_path):
    """The same task id in one inbox executes once."""
    from scripts.courier_mailbox import process_inbox

    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "home"
    task = {
        "task_id": "mission-same",
        "name": "same task twice",
        "estimated_cost_eur": 0.0,
        "status": "PENDING",
    }
    inbox.write_text(json.dumps(task) + "\n" + json.dumps(task) + "\n", encoding="utf-8")
    results = process_inbox(inbox, outbox, home_path=home)
    assert len(results) == 1
    out_lines = [line for line in outbox.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(out_lines) == 1
    assert json.loads(out_lines[0])["task_id"] == "mission-same"


def test_synthetic_a_to_b_two_agents_zero_eur(tmp_path, capsys):
    """Synthetic A→B: two agent identities, 0 EUR, no network provider."""
    path = tmp_path / "coordination_ledger.jsonl"
    store = FileCoordinationStore(path)
    reducer = reduce_store(store)
    windows = _event(
        "ab-win", "mission-ab", AgentID.GOOGLE_WINDOWS, "GOOGLE_WINDOWS", "2026-10-22T09:00:00Z",
    )
    mac = _event(
        "ab-mac", "mission-ab", AgentID.MUSE_MAC, "MUSE_MAC", "2026-10-22T09:01:00Z",
        event_type=EventType.PARTIAL,
    )
    assert _write_new(store, reducer, windows) is True
    assert _write_new(store, reducer, mac) is False
    assert path.read_text(encoding="utf-8").count("\n") == 1

    leases = LeaseStore(str(tmp_path / "agents.db"))
    try:
        held = leases.acquire("repo://ab", "agent-windows", "wk-ab", ttl_s=60)
        with pytest.raises(Exception):
            leases.acquire("repo://ab", "agent-mac", "wk-ab", ttl_s=60)
        checked = leases.check_write("repo://ab", held.token, "agent-windows")
        assert checked.holder == "agent-windows"
        with pytest.raises(StaleLease):
            leases.check_write("repo://ab", held.token, "agent-mac")
    finally:
        leases.close()

    allowed = CostGate.evaluate_spend_request("google_antigravity_plus", estimated_cost_eur=0.0)
    blocked = CostGate.evaluate_spend_request("google_antigravity_plus")
    assert allowed["allowed"] is True
    assert blocked["allowed"] is False
    assert blocked["reason"] == "UNKNOWN_COST"

    from scripts.courier_mailbox import process_inbox

    inbox = tmp_path / "inbox.jsonl"
    outbox = tmp_path / "outbox.jsonl"
    home = tmp_path / "chip-home"
    line = json.dumps({
        "task_id": "ab-chip",
        "name": "synthetic",
        "estimated_cost_eur": 0.0,
        "status": "PENDING",
    })
    inbox.write_text(line + "\n" + line + "\n", encoding="utf-8")
    results = process_inbox(inbox, outbox, home_path=home)
    assert len(results) == 1
    assert results[0]["execution_result"]["cost_eur"] == 0.0
    assert results[0]["execution_result"]["verifier_result"]["resolution"] == "verified"

    print("A_TO_B_SYNTHETIC=VERIFIED")
    print("A_TO_B_REAL_PROVIDER=NOT_TESTED")
    print("LEASE_FENCING=VERIFIED")
    print("COST_GATE=VERIFIED")
    print("LEDGER=VERIFIED")
    print("IDEMPOTENCY=VERIFIED")
    print("COST_EUR=0")
    print("AGENTS=GOOGLE_WINDOWS,MUSE_MAC")
    captured = capsys.readouterr()
    assert "A_TO_B_SYNTHETIC=VERIFIED" in captured.out
    assert "A_TO_B_REAL_PROVIDER=NOT_TESTED" in captured.out
    sys.stderr.write(captured.out)
