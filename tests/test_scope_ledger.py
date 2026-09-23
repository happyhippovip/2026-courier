"""Tests for scripts/scope_ledger.py.

Covers:
  - Exclusive write-write conflict on same scope
  - Parent/child path overlap (directory contains file)
  - READ-READ is allowed (concurrent reads)
  - READ-WRITE conflicts both ways
  - Expired lease allows re-acquisition
  - Fencing token: expired is rejected, valid is accepted
  - reconcile_crashed_worker() expires all active leases for a worker
  - Disjoint scopes don't conflict
"""

import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO / "scripts"))

from scope_ledger import ScopeLedger


@pytest.fixture
def ledger(tmp_path):
    db = str(tmp_path / "test.sqlite3")
    return ScopeLedger(db)


# ─── Write-write conflict ────────────────────────────────────────────────────

def test_write_write_same_scope_denied(ledger):
    l1 = ledger.acquire_lease("/data/file.txt", "WRITE", "t1", "e1", "w1")
    assert l1 is not None, "first WRITE lease should be granted"
    l2 = ledger.acquire_lease("/data/file.txt", "WRITE", "t2", "e2", "w2")
    assert l2 is None, "second WRITE on same scope must be denied"


def test_write_write_parent_child_scope_denied(ledger):
    """Writing to /foo blocks writing to /foo/bar (parent owns child)."""
    l1 = ledger.acquire_lease("/foo", "WRITE", "t1", "e1", "w1")
    assert l1 is not None
    l2 = ledger.acquire_lease("/foo/bar", "WRITE", "t2", "e2", "w2")
    assert l2 is None, "child write under active parent write must be denied"


def test_write_child_blocks_parent_write(ledger):
    """Writing to /foo/bar blocks writing to /foo (child owns parent)."""
    l1 = ledger.acquire_lease("/foo/bar", "WRITE", "t1", "e1", "w1")
    assert l1 is not None
    l2 = ledger.acquire_lease("/foo", "WRITE", "t2", "e2", "w2")
    assert l2 is None, "parent write while child is active must be denied"


def test_write_disjoint_scopes_allowed(ledger):
    l1 = ledger.acquire_lease("/scope/A", "WRITE", "t1", "e1", "w1")
    l2 = ledger.acquire_lease("/scope/B", "WRITE", "t2", "e2", "w2")
    assert l1 is not None
    assert l2 is not None, "disjoint scopes must not conflict"


# ─── Read-write conflicts ────────────────────────────────────────────────────

def test_read_blocks_write_on_same_scope(ledger):
    """An active READ lease prevents a WRITE on the same scope."""
    l1 = ledger.acquire_lease("/shared", "READ", "t1", "e1", "w1")
    assert l1 is not None
    l2 = ledger.acquire_lease("/shared", "WRITE", "t2", "e2", "w2")
    assert l2 is None, "WRITE must not be granted while READ is active"


def test_write_blocks_subsequent_read(ledger):
    """An active WRITE lease prevents a READ on the same scope."""
    l1 = ledger.acquire_lease("/exclusive", "WRITE", "t1", "e1", "w1")
    assert l1 is not None
    l2 = ledger.acquire_lease("/exclusive", "READ", "t2", "e2", "w2")
    assert l2 is None, "READ must not be granted while WRITE is active"


def test_concurrent_reads_allowed(ledger):
    """Multiple READ leases on the same scope must all be granted."""
    l1 = ledger.acquire_lease("/readable", "READ", "t1", "e1", "w1")
    l2 = ledger.acquire_lease("/readable", "READ", "t2", "e2", "w2")
    l3 = ledger.acquire_lease("/readable", "READ", "t3", "e3", "w3")
    assert l1 is not None
    assert l2 is not None
    assert l3 is not None


# ─── Lease expiry ────────────────────────────────────────────────────────────

def test_expired_lease_allows_reacquisition(ledger):
    l1 = ledger.acquire_lease("/expiring", "WRITE", "t1", "e1", "w1", ttl=0.05)
    assert l1 is not None
    time.sleep(0.1)  # Wait for lease to expire
    l2 = ledger.acquire_lease("/expiring", "WRITE", "t2", "e2", "w2")
    assert l2 is not None, "WRITE on expired scope must be granted"


def test_fencing_token_invalid_after_expiry(ledger):
    l1 = ledger.acquire_lease("/fence", "WRITE", "t1", "e1", "w1", ttl=0.05)
    assert l1 is not None
    time.sleep(0.1)
    assert ledger.verify_fencing_token(l1["fencing_token"]) is False


def test_fencing_token_valid_for_active_lease(ledger):
    l1 = ledger.acquire_lease("/fence_active", "WRITE", "t1", "e1", "w1", ttl=60)
    assert l1 is not None
    assert ledger.verify_fencing_token(l1["fencing_token"]) is True


def test_new_holder_has_valid_fencing_token_after_expiry(ledger):
    l1 = ledger.acquire_lease("/fence2", "WRITE", "t1", "e1", "w1", ttl=0.05)
    time.sleep(0.1)
    l2 = ledger.acquire_lease("/fence2", "WRITE", "t2", "e2", "w2", ttl=60)
    assert l2 is not None
    assert ledger.verify_fencing_token(l2["fencing_token"]) is True
    # Old token must still be rejected
    assert ledger.verify_fencing_token(l1["fencing_token"]) is False


def test_bogus_fencing_token_rejected(ledger):
    assert ledger.verify_fencing_token("not-a-real-token") is False


# ─── reconcile_crashed_worker() ──────────────────────────────────────────────

def test_reconcile_crashed_worker_releases_all_leases(ledger):
    l1 = ledger.acquire_lease("/crash/A", "WRITE", "t1", "e1", "crashed-worker", ttl=60)
    l2 = ledger.acquire_lease("/crash/B", "WRITE", "t2", "e2", "crashed-worker", ttl=60)
    assert l1 is not None
    assert l2 is not None

    ledger.reconcile_crashed_worker("crashed-worker")

    # Fencing tokens for crashed worker must now be invalid
    assert ledger.verify_fencing_token(l1["fencing_token"]) is False
    assert ledger.verify_fencing_token(l2["fencing_token"]) is False


def test_reconcile_crashed_worker_allows_reacquisition(ledger):
    l1 = ledger.acquire_lease("/post_crash", "WRITE", "t1", "e1", "crashed-worker", ttl=60)
    assert l1 is not None

    ledger.reconcile_crashed_worker("crashed-worker")

    l2 = ledger.acquire_lease("/post_crash", "WRITE", "t2", "e2", "new-worker", ttl=60)
    assert l2 is not None, "scope must be acquirable after worker crash-reconcile"


def test_reconcile_does_not_affect_other_workers(ledger):
    l1 = ledger.acquire_lease("/shared_space", "WRITE", "t1", "e1", "good-worker", ttl=60)
    l2 = ledger.acquire_lease("/other_space", "WRITE", "t2", "e2", "crashed-worker", ttl=60)

    ledger.reconcile_crashed_worker("crashed-worker")

    # good-worker's lease must remain valid
    assert ledger.verify_fencing_token(l1["fencing_token"]) is True
    assert ledger.verify_fencing_token(l2["fencing_token"]) is False


# ─── Lease metadata ──────────────────────────────────────────────────────────

def test_lease_has_required_fields(ledger):
    l1 = ledger.acquire_lease("/meta", "WRITE", "t1", "e1", "w1", ttl=60)
    assert "lease_id" in l1
    assert "fencing_token" in l1
    assert "expires_at" in l1
    assert l1["expires_at"] > time.time()
