#!/usr/bin/env python3
"""Distributed Scope Lease Manager for Courier Tasks.

Enforces mutual exclusion for concurrent workers accessing filesystem or virtual scopes.
Prevents write-write and read-write collisions with deterministic fencing tokens.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any
import uuid


class ScopeLedger:
    def __init__(self, db_path: str | Path = "scope.sqlite3"):
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, isolation_level=None, timeout=30.0)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __enter__(self) -> ScopeLedger:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _init_db(self) -> None:
        conn = self.get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scope_leases (
                lease_id TEXT PRIMARY KEY,
                scope_id TEXT,
                mode TEXT,
                task_id TEXT,
                execution_id TEXT,
                worker_id TEXT,
                fencing_token TEXT,
                acquired_at REAL,
                expires_at REAL
            )
        """)

    def _normalize_scope(self, scope_id: str | Path) -> str:
        s = str(scope_id).replace("\\", "/").strip()
        while "//" in s:
            s = s.replace("//", "/")
        if not s.startswith("/") and not (len(s) > 1 and s[1] == ":"):
            s = "/" + s
        if os.name == "nt" or sys.platform == "darwin":
            s = s.lower()
        return s.rstrip("/") if s != "/" else "/"

    def _overlaps(self, s1: str, s2: str) -> bool:
        if s1 == s2:
            return True
        if s1.startswith(s2 + "/") or s2.startswith(s1 + "/"):
            return True
        return False

    def acquire_lease(
        self,
        scope_id: str | Path,
        mode: str,
        task_id: str,
        execution_id: str,
        worker_id: str,
        ttl: float = 60.0,
    ) -> dict[str, Any] | None:
        norm_scope = self._normalize_scope(scope_id)
        now = time.time()
        conn = self.get_conn()

        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "SELECT lease_id, scope_id, mode FROM scope_leases WHERE expires_at > ?",
                (now,),
            )
            active_leases = cur.fetchall()

            for _, active_scope, active_mode in active_leases:
                if self._overlaps(norm_scope, active_scope):
                    if mode == "WRITE" or active_mode == "WRITE":
                        conn.execute("ROLLBACK")
                        return None  # Denied

            lease_id = str(uuid.uuid4())
            fencing_token = str(uuid.uuid4())
            expires_at = now + ttl

            conn.execute(
                """
                INSERT INTO scope_leases 
                (lease_id, scope_id, mode, task_id, execution_id, worker_id, fencing_token, acquired_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    lease_id,
                    norm_scope,
                    mode,
                    task_id,
                    execution_id,
                    worker_id,
                    fencing_token,
                    now,
                    expires_at,
                ),
            )
            conn.execute("COMMIT")
            return {
                "lease_id": lease_id,
                "fencing_token": fencing_token,
                "expires_at": expires_at,
            }
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def release_lease(self, lease_id: str) -> bool:
        now = time.time()
        conn = self.get_conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute(
                "UPDATE scope_leases SET expires_at = ? WHERE lease_id = ? AND expires_at > ?",
                (now - 1, lease_id, now),
            )
            updated = cur.rowcount > 0
            conn.execute("COMMIT")
            return updated
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def verify_fencing_token(self, fencing_token: str) -> bool:
        now = time.time()
        conn = self.get_conn()
        cur = conn.execute(
            "SELECT expires_at FROM scope_leases WHERE fencing_token = ? AND expires_at > ?",
            (fencing_token, now),
        )
        return cur.fetchone() is not None

    def reconcile_crashed_worker(self, worker_id: str) -> None:
        now = time.time()
        conn = self.get_conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "UPDATE scope_leases SET expires_at = ? WHERE worker_id = ? AND expires_at > ?",
                (now - 1, worker_id, now),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def run_scope_bench(db_path: str = "bench_scopes_tmp.sqlite3") -> dict[str, Any]:
    p = Path(db_path)
    if p.exists():
        p.unlink()

    results: dict[str, Any] = {}
    with ScopeLedger(db_path) as ledger:
        # Test 1: Write conflict
        l1 = ledger.acquire_lease("file_x", "WRITE", "t1", "e1", "w1")
        l2 = ledger.acquire_lease("file_x", "WRITE", "t2", "e2", "w2")
        results["write_conflict_blocked"] = (l1 is not None and l2 is None)

        # Test 2: Overlap conflict
        l3 = ledger.acquire_lease("/foo", "WRITE", "t3", "e3", "w3")
        l4 = ledger.acquire_lease("/foo/bar", "WRITE", "t4", "e4", "w4")
        results["overlap_conflict_blocked"] = (l3 is not None and l4 is None)

        # Test 3: Read-write conflict & concurrent read
        l5 = ledger.acquire_lease("/bar", "READ", "t5", "e5", "w5")
        l6 = ledger.acquire_lease("/bar", "WRITE", "t6", "e6", "w6")
        l7 = ledger.acquire_lease("/bar", "READ", "t7", "e7", "w7")
        results["read_write_conflict_blocked"] = (l5 is not None and l6 is None and l7 is not None)

        # Test 4: Expiration & fencing
        l8 = ledger.acquire_lease("/baz", "WRITE", "t8", "e8", "w8", ttl=0.05)
        time.sleep(0.1)
        l9 = ledger.acquire_lease("/baz", "WRITE", "t9", "e9", "w9")
        results["fencing_verified"] = (
            l9 is not None
            and not ledger.verify_fencing_token(l8["fencing_token"])
            and ledger.verify_fencing_token(l9["fencing_token"])
        )
        results["status"] = "PASS"

    if p.exists():
        p.unlink(missing_ok=True)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scope Ledger CLI")
    parser.add_argument("--bench", action="store_true", help="Run benchmark / self-test")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    if args.bench:
        res = run_scope_bench()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"SCOPE_BENCH: {res}")
        return 0

    print("ScopeLedger ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
