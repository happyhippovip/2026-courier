"""Tests for courier_core.fencing_token - Distributed Lease Fence Token & Split-Brain Prevention Guard."""

from __future__ import annotations

import json
import pytest

from courier_core.fencing_token import (
    FencingTokenManager,
    StaleFencingTokenError,
    LeaseConflictError,
    main,
)


def test_monotonic_token_generation_and_validation(tmp_path):
    state_file = tmp_path / "fences.json"
    mgr = FencingTokenManager(state_file)

    rec1 = mgr.acquire(resource_id="res-order-1", holder="worker-alpha", ttl_seconds=10.0)
    assert rec1.generation == 1
    assert rec1.holder == "worker-alpha"

    # Commit with generation 1
    assert mgr.validate_and_commit(resource_id="res-order-1", generation=1) is True

    # Release and acquire with new worker
    mgr.release(resource_id="res-order-1", holder="worker-alpha")
    rec2 = mgr.acquire(resource_id="res-order-1", holder="worker-beta", ttl_seconds=10.0)
    assert rec2.generation == 2
    assert rec2.holder == "worker-beta"

    # Commit with generation 2
    assert mgr.validate_and_commit(resource_id="res-order-1", generation=2) is True


def test_split_brain_stale_token_rejection(tmp_path):
    state_file = tmp_path / "fences.json"
    mgr = FencingTokenManager(state_file)

    # Worker 1 gets token 1
    mgr.acquire(resource_id="res-database-shard-A", holder="worker-zombie", ttl_seconds=1.0)
    mgr.release(resource_id="res-database-shard-A", holder="worker-zombie")

    # Worker 2 takes over and gets token 2
    mgr.acquire(resource_id="res-database-shard-A", holder="worker-primary", ttl_seconds=10.0)
    mgr.validate_and_commit(resource_id="res-database-shard-A", generation=2)

    # Delayed Zombie Worker 1 wakes up and attempts to write with stale token 1 -> MUST BE REJECTED
    with pytest.raises(StaleFencingTokenError, match="Stale fencing token 1 rejected"):
        mgr.validate_and_commit(resource_id="res-database-shard-A", generation=1)


def test_lease_conflict_rejection(tmp_path):
    state_file = tmp_path / "fences.json"
    mgr = FencingTokenManager(state_file)

    mgr.acquire(resource_id="res-task-99", holder="holder-A", ttl_seconds=100.0)

    # Second holder attempts to acquire while holder-A has active lease
    with pytest.raises(LeaseConflictError, match="Resource is currently leased to holder-A"):
        mgr.acquire(resource_id="res-task-99", holder="holder-B", ttl_seconds=100.0)


def test_expired_lease_allows_takeover(tmp_path):
    state_file = tmp_path / "fences.json"
    mgr = FencingTokenManager(state_file)

    t0 = 1000.0
    rec1 = mgr.acquire(resource_id="res-ephemeral", holder="holder-1", ttl_seconds=5.0, now=t0)
    assert rec1.generation == 1

    # Expired lease cannot commit
    with pytest.raises(StaleFencingTokenError, match="lease expired"):
        mgr.validate_and_commit(resource_id="res-ephemeral", generation=1, now=t0 + 6.0)

    # Unknown resource cannot create phantom commit
    with pytest.raises(StaleFencingTokenError, match="no active lease"):
        mgr.validate_and_commit(resource_id="res-unknown", generation=1, now=t0)

    # At t0 + 10s, lease has expired -> holder-2 takes over with generation 2
    rec2 = mgr.acquire(resource_id="res-ephemeral", holder="holder-2", ttl_seconds=5.0, now=t0 + 10.0)
    assert rec2.generation == 2
    assert rec2.holder == "holder-2"


def test_cli_fencing_token(tmp_path, monkeypatch, capsys):
    state_file = tmp_path / "cli_fences.json"

    # Acquire
    monkeypatch.setattr(
        "sys.argv",
        [
            "fencing_token.py",
            "acquire",
            "--file",
            str(state_file),
            "--resource",
            "cli-res-1",
            "--holder",
            "cli-worker-1",
            "--ttl",
            "30",
        ],
    )
    main()
    out = capsys.readouterr().out
    assert "generation=1" in out

    # Validate
    monkeypatch.setattr(
        "sys.argv",
        [
            "fencing_token.py",
            "validate",
            "--file",
            str(state_file),
            "--resource",
            "cli-res-1",
            "--generation",
            "1",
        ],
    )
    main()
    out = capsys.readouterr().out
    assert "TOKEN_COMMITTED_OK" in out


def test_fencing_token_owner_validation_rejects_foreign_worker(tmp_path):
    from courier_core.fencing_token import FencingTokenManager, StaleFencingTokenError

    mgr = FencingTokenManager(tmp_path / "fences.json")
    rec = mgr.acquire(resource_id="res-owner-check", holder="owner-legit", ttl_seconds=60.0)
    assert rec.generation == 1

    # Same holder commits successfully
    assert mgr.validate_and_commit(resource_id="res-owner-check", generation=1, holder="owner-legit") is True

    # Foreign imposter with correct generation is rejected
    with pytest.raises(StaleFencingTokenError, match="holder mismatch"):
        mgr.validate_and_commit(resource_id="res-owner-check", generation=1, holder="imposter-worker")


def test_fencing_token_stale_generation_release_prevented(tmp_path):
    from courier_core.fencing_token import FencingTokenManager

    mgr = FencingTokenManager(tmp_path / "fences.json")
    rec1 = mgr.acquire(resource_id="res-gen-check", holder="worker-alpha", ttl_seconds=60.0)
    assert rec1.generation == 1

    # Stale release call passing old generation 0 fails
    assert mgr.release(resource_id="res-gen-check", holder="worker-alpha", generation=0) is False
    assert mgr.inspect("res-gen-check")["expires_at"] > 0

    # Matching generation release succeeds
    assert mgr.release(resource_id="res-gen-check", holder="worker-alpha", generation=1) is True
    assert mgr.inspect("res-gen-check")["expires_at"] == 0.0


def test_fencing_token_rejects_empty_or_nul_parameters(tmp_path):
    from courier_core.fencing_token import FencingTokenManager, FencingError

    mgr = FencingTokenManager(tmp_path / "fences.json")
    with pytest.raises(FencingError, match="resource_id"):
        mgr.acquire(resource_id="   ", holder="w1")
    with pytest.raises(FencingError, match="resource_id"):
        mgr.acquire(resource_id="bad\x00res", holder="w1")
    with pytest.raises(FencingError, match="holder"):
        mgr.acquire(resource_id="res-1", holder="")
    with pytest.raises(FencingError, match="holder"):
        mgr.acquire(resource_id="res-1", holder="bad\x00holder")
