from __future__ import annotations

import json
from pathlib import Path
import time

import pytest

import scripts.scope_ledger as sl
from scripts.scope_ledger import ScopeLedger


def test_scope_ledger_init_and_close(tmp_path: Path):
    db_file = tmp_path / "scope.sqlite3"
    with ScopeLedger(db_file) as ledger:
        conn = ledger.get_conn()
        cur = conn.execute("PRAGMA journal_mode")
        assert cur.fetchone()[0].upper() == "WAL"

    # Connection closed, file unlinking succeeds without WinError 32
    db_file.unlink()
    assert not db_file.exists()


def test_scope_normalization_and_overlaps(tmp_path: Path):
    with ScopeLedger(tmp_path / "scope.sqlite3") as ledger:
        s1 = ledger._normalize_scope("C:\\Users\\test\\project")
        assert "\\" not in s1
        assert s1.startswith("c:/") or s1.startswith("/c:")

        assert ledger._overlaps("/foo", "/foo") is True
        assert ledger._overlaps("/foo/bar", "/foo") is True
        assert ledger._overlaps("/foo", "/foo/bar") is True
        assert ledger._overlaps("/foo/bar", "/foo/baz") is False


def test_exclusive_write_leases(tmp_path: Path):
    with ScopeLedger(tmp_path / "scope.sqlite3") as ledger:
        l1 = ledger.acquire_lease("/data/output", "WRITE", "t1", "e1", "w1", ttl=30.0)
        assert l1 is not None
        assert "fencing_token" in l1

        # Second write to same scope is denied
        l2 = ledger.acquire_lease("/data/output", "WRITE", "t2", "e2", "w2", ttl=30.0)
        assert l2 is None

        # Write to subscope is also denied
        l3 = ledger.acquire_lease("/data/output/subfile.txt", "WRITE", "t3", "e3", "w3", ttl=30.0)
        assert l3 is None


def test_read_write_mutual_exclusion(tmp_path: Path):
    with ScopeLedger(tmp_path / "scope.sqlite3") as ledger:
        # Multiple reads on same scope are allowed
        r1 = ledger.acquire_lease("/shared/repo", "READ", "t1", "e1", "w1", ttl=30.0)
        r2 = ledger.acquire_lease("/shared/repo", "READ", "t2", "e2", "w2", ttl=30.0)
        assert r1 is not None
        assert r2 is not None

        # Write on scope with active reads is denied
        w1 = ledger.acquire_lease("/shared/repo", "WRITE", "t3", "e3", "w3", ttl=30.0)
        assert w1 is None


def test_release_lease(tmp_path: Path):
    with ScopeLedger(tmp_path / "scope.sqlite3") as ledger:
        l1 = ledger.acquire_lease("/lock/test", "WRITE", "t1", "e1", "w1", ttl=30.0)
        assert l1 is not None

        # Release lease
        released = ledger.release_lease(l1["lease_id"])
        assert released is True

        # Now another worker can acquire it immediately
        l2 = ledger.acquire_lease("/lock/test", "WRITE", "t2", "e2", "w2", ttl=30.0)
        assert l2 is not None


def test_reconcile_crashed_worker(tmp_path: Path):
    with ScopeLedger(tmp_path / "scope.sqlite3") as ledger:
        l1 = ledger.acquire_lease("/worker/test", "WRITE", "t1", "e1", "w_crash", ttl=60.0)
        assert l1 is not None
        assert ledger.verify_fencing_token(l1["fencing_token"]) is True

        # Crash recovery for w_crash
        ledger.reconcile_crashed_worker("w_crash")
        assert ledger.verify_fencing_token(l1["fencing_token"]) is False

        # Can now be claimed by new worker
        l2 = ledger.acquire_lease("/worker/test", "WRITE", "t2", "e2", "w_new", ttl=60.0)
        assert l2 is not None


def test_run_scope_bench(tmp_path: Path):
    db_file = tmp_path / "bench_scope.sqlite3"
    res = sl.run_scope_bench(str(db_file))
    assert res["status"] == "PASS"
    assert res["write_conflict_blocked"] is True
    assert res["overlap_conflict_blocked"] is True
    assert res["read_write_conflict_blocked"] is True
    assert res["fencing_verified"] is True


def test_main_cli(capsys):
    code = sl.main(["--bench", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "PASS"
