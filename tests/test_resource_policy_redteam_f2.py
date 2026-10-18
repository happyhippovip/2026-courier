"""Red-Team R1 F2: a task lease must be owned by one runner instance.

Two runners for the same agent name must not both "own" one task, and a
renewal must not let the same owner run a different input under the lease.
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.resource_policy import TaskLeaseManager


def _repo(tmp_path):
    for sub in ("locks", "policies", "processed", "approvals", "chief-decisions"):
        (tmp_path / "events" / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_task_lease_same_owner_different_input_is_not_a_renewal(tmp_path):
    m = TaskLeaseManager(repo_dir=tmp_path)
    assert m.acquire_lease("t", "hashA", "agent#run1")[0] is True
    assert m.acquire_lease("t", "hashB", "agent#run1")[0] is False


def test_same_owner_same_input_still_renews(tmp_path):
    m = TaskLeaseManager(repo_dir=tmp_path)
    assert m.acquire_lease("t", "hashA", "agent#run1")[0] is True
    ok, reason, _ = m.acquire_lease("t", "hashA", "agent#run1")
    assert ok is True
    assert reason == "LEASE_RENEWED"


def test_two_loop_instances_for_same_agent_do_not_share_a_lease(tmp_path):
    from scripts.run_autonomous_loop import AutonomousLevel6Loop
    repo = _repo(tmp_path)
    a = AutonomousLevel6Loop(repo_dir=repo)
    b = AutonomousLevel6Loop(repo_dir=repo)
    owner_a = a._lease_owner("codex-builder")
    owner_b = b._lease_owner("codex-builder")
    assert owner_a != owner_b
    assert owner_a.startswith("codex-builder#")
    # Same task, same input: runner B must not "renew" runner A's lease ...
    assert a.lease_manager.acquire_lease("t", "hashA", owner_a)[0] is True
    assert b.lease_manager.acquire_lease("t", "hashA", owner_b)[0] is False
    # ... and B's release must not delete A's lease.
    b.lease_manager.release_lease("t", owner_b)
    assert a.lease_manager._get_lease_path("t").exists()
