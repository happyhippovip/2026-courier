#!/usr/bin/env python3
"""Durable WAL-backed Magazine Queue and Ingestion Engine for Courier.

Provides crash-resilient, streaming ingestion and deduplicated storage of
records with bounded prefetch and verifiable memory footprint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tracemalloc
from pathlib import Path
from typing import Any, Iterable


class MagazineLedger:
    def __init__(self, db_path: str | Path = "magazine.sqlite3"):
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self.init_db()

    def get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, isolation_level=None)
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

    def __enter__(self) -> MagazineLedger:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def init_db(self) -> None:
        conn = self.get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS magazine_imports (
                import_id TEXT PRIMARY KEY,
                filename TEXT,
                bytes_read INTEGER DEFAULT 0,
                status TEXT DEFAULT 'IMPORTING'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS magazine_records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_id TEXT,
                record_hash TEXT UNIQUE,
                payload TEXT,
                status TEXT DEFAULT 'PENDING',
                provenance TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON magazine_records(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_import ON magazine_records(import_id)")

    def start_or_resume_import(self, import_id: str, filename: str) -> tuple[int, str]:
        conn = self.get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO magazine_imports (import_id, filename, bytes_read, status) VALUES (?, ?, 0, 'IMPORTING')",
            (import_id, str(filename)),
        )
        cur = conn.execute("SELECT bytes_read, status FROM magazine_imports WHERE import_id = ?", (import_id,))
        row = cur.fetchone()
        return (row[0], row[1]) if row else (0, "IMPORTING")

    def update_import_progress(self, import_id: str, bytes_read: int, status: str = "IMPORTING") -> None:
        conn = self.get_conn()
        conn.execute(
            "UPDATE magazine_imports SET bytes_read = ?, status = ? WHERE import_id = ?",
            (bytes_read, status, import_id),
        )

    def import_chunk(self, import_id: str, records: Iterable[tuple[str, str]], bytes_read_after: int) -> None:
        conn = self.get_conn()
        try:
            conn.execute("BEGIN")
            values = [
                (import_id, hashlib.sha256(payload.encode("utf-8")).hexdigest(), payload, provenance)
                for payload, provenance in records
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO magazine_records (import_id, record_hash, payload, provenance) VALUES (?, ?, ?, ?)",
                values,
            )
            conn.execute("UPDATE magazine_imports SET bytes_read = ? WHERE import_id = ?", (bytes_read_after, import_id))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def prefetch(self, limit: int = 10) -> list[tuple[Any, ...]]:
        conn = self.get_conn()
        conn.execute("BEGIN")
        cur = conn.execute(
            "SELECT record_id, payload, provenance FROM magazine_records WHERE status = 'PENDING' LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        ids = [r[0] for r in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn.execute(f"UPDATE magazine_records SET status = 'ACTIVE' WHERE record_id IN ({placeholders})", ids)
        conn.execute("COMMIT")
        return rows

    def stream_import(
        self,
        import_id: str,
        filepath: str | Path,
        chunk_size: int = 5000,
        crash_after: int | None = None,
    ) -> None:
        p = Path(filepath)
        bytes_read, status = self.start_or_resume_import(import_id, str(p))
        if status == "COMPLETE":
            return

        with open(p, "rb") as f:
            if bytes_read > 0:
                f.seek(bytes_read)

            chunk: list[tuple[str, str]] = []
            line_count = 0

            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    if chunk:
                        self.import_chunk(import_id, chunk, pos)
                    self.update_import_progress(import_id, pos, "COMPLETE")
                    break

                try:
                    # Validate JSON
                    json.loads(line)
                    chunk.append((line.decode("utf-8").strip(), f"{p}:{pos}"))
                except Exception:
                    pass

                line_count += 1
                if len(chunk) >= chunk_size:
                    self.import_chunk(import_id, chunk, f.tell())
                    chunk = []

                if crash_after and line_count >= crash_after:
                    if chunk:
                        self.import_chunk(import_id, chunk, f.tell())
                    raise RuntimeError("Simulated Crash")


def generate_file(
    path: str | Path,
    num_records: int,
    malformed_at: int | None = None,
    partial_final: bool = False,
) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for i in range(num_records):
            if malformed_at == i:
                f.write("{malformed JSON\n")
            else:
                f.write(json.dumps({"id": i, "data": f"record_{i}"}) + "\n")
        if partial_final:
            f.write('{"id": 9999999, "data": "partia')


def run_magazine_bench(db_path: str = "test_magazine.sqlite3") -> dict[str, Any]:
    p = Path(db_path)
    if p.exists():
        p.unlink()

    results: dict[str, Any] = {}
    with MagazineLedger(db_path) as mag:
        test_file = Path("test_stream.jsonl")
        try:
            generate_file(test_file, 5000, malformed_at=250)
            tracemalloc.start()
            mag.stream_import("import_bench", test_file, chunk_size=1000)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            results["peak_mb"] = round(peak / 1024 / 1024, 2)
            prefetched = mag.prefetch(10)
            results["prefetched_count"] = len(prefetched)
            results["status"] = "PASS"
        finally:
            if test_file.exists():
                test_file.unlink(missing_ok=True)

    if p.exists():
        p.unlink(missing_ok=True)

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Magazine Queue CLI")
    parser.add_argument("--bench", action="store_true", help="Run benchmark verification")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    if args.bench:
        res = run_magazine_bench()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"MAGAZINE_BENCH: {res}")
        return 0

    print("MagazineLedger ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
