"""A Windows delete-pending reclaim lock is a lost race, not a second claim."""
import json
import os
from pathlib import Path

from scripts.resource_policy import TaskLeaseManager


def _seed_expired(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "task_id": "TASK-PERM",
        "task_hash": "old",
        "owner_id": "old-owner",
        "expires_at": 1,
    }), encoding="utf-8")


def test_permission_error_then_retry_still_reclaims_once(tmp_path, monkeypatch):
    mgr = TaskLeaseManager(repo_dir=tmp_path)
    lease_path = mgr._get_lease_path("TASK-PERM")
    _seed_expired(lease_path)
    real_open = os.open
    seen = {"n": 0}

    def wrapped(path, flags, mode=0o777):
        if str(path).endswith(".reclaim.lock"):
            seen["n"] += 1
            if seen["n"] == 1:
                raise PermissionError("delete pending")
        return real_open(path, flags, mode)

    monkeypatch.setattr(os, "open", wrapped)
    ok, reason, data = mgr.acquire_lease("TASK-PERM", "hash", "reclaimer", duration_sec=60)
    assert ok is True
    assert reason == "LEASE_RECLAIMED_EXPIRED"
    assert data["owner_id"] == "reclaimer"
    assert seen["n"] == 2


def test_permission_error_after_someone_else_renewed_does_not_claim(tmp_path, monkeypatch):
    mgr = TaskLeaseManager(repo_dir=tmp_path)
    lease_path = mgr._get_lease_path("TASK-PERM")
    _seed_expired(lease_path)
    real_open = os.open

    def wrapped(path, flags, mode=0o777):
        if str(path).endswith(".reclaim.lock"):
            renewed = json.loads(lease_path.read_text(encoding="utf-8"))
            renewed["owner_id"] = "other"
            renewed["expires_at"] = 9_999_999_999
            lease_path.write_text(json.dumps(renewed), encoding="utf-8")
            raise PermissionError("delete pending")
        return real_open(path, flags, mode)

    monkeypatch.setattr(os, "open", wrapped)
    ok, reason, data = mgr.acquire_lease("TASK-PERM", "hash", "reclaimer", duration_sec=60)
    assert ok is False
    assert reason == "TASK_ALREADY_CLAIMED_BY_ANOTHER_BUILDER"
    assert data["owner_id"] == "other"
