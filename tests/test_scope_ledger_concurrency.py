"""Concurrent acquisition races for ScopeLedger (SQLite BEGIN IMMEDIATE).

Exactly one WRITE lease may be granted per scope under thread concurrency;
fencing tokens of the winner stay valid, losers get no lease at all.
"""
import os
import sys
import threading

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.scope_ledger import ScopeLedger


def _race_acquire(ledger, scope, mode, n, prefix):
    barrier = threading.Barrier(n)
    results = [None] * n

    def worker(i):
        barrier.wait()
        results[i] = ledger.acquire_lease(
            scope, mode, f"t-{prefix}-{i}", f"e-{prefix}-{i}", f"w-{prefix}-{i}"
        )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_concurrent_write_write_single_winner(tmp_path):
    ledger = ScopeLedger(str(tmp_path / "scopes.sqlite3"))
    results = _race_acquire(ledger, "/race/scope", "WRITE", 16, "ww")
    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    assert ledger.verify_fencing_token(winners[0]["fencing_token"])


def test_concurrent_read_write_single_writer(tmp_path):
    ledger = ScopeLedger(str(tmp_path / "scopes.sqlite3"))
    results = _race_acquire(ledger, "/race/mixed", "WRITE", 8, "w")
    results += _race_acquire(ledger, "/race/mixed", "READ", 8, "r")
    granted_writes = [r for r in results[:8] if r is not None]
    # Either the single writer won (reads denied) or a read won first
    # (writer denied); concurrent writers must never double-grant.
    assert len(granted_writes) <= 1


def test_concurrent_overlap_single_winner(tmp_path):
    ledger = ScopeLedger(str(tmp_path / "scopes.sqlite3"))
    barrier = threading.Barrier(2)
    results = [None, None]

    def worker(i, scope):
        barrier.wait()
        results[i] = ledger.acquire_lease(
            scope, "WRITE", f"t-ov-{i}", f"e-ov-{i}", f"w-ov-{i}"
        )

    threads = [
        threading.Thread(target=worker, args=(0, "/ov/parent")),
        threading.Thread(target=worker, args=(1, "/ov/parent/child")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(r is not None for r in results) == 1
