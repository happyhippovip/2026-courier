from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.magazine as mag


def test_magazine_init_and_close(tmp_path: Path):
    db_file = tmp_path / "test.sqlite3"
    with mag.MagazineLedger(db_file) as ledger:
        conn = ledger.get_conn()
        cur = conn.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        assert mode.upper() == "WAL"

    # Connection closed, DB file unremovable test on Windows succeeds
    db_file.unlink()
    assert not db_file.exists()


def test_generate_file(tmp_path: Path):
    out = tmp_path / "data.jsonl"
    mag.generate_file(out, num_records=5, malformed_at=2, partial_final=True)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    assert lines[2] == "{malformed JSON"
    assert "9999999" in lines[5]


def test_stream_import_and_prefetch(tmp_path: Path):
    db_file = tmp_path / "queue.sqlite3"
    data_file = tmp_path / "stream.jsonl"
    mag.generate_file(data_file, num_records=100, malformed_at=10)

    with mag.MagazineLedger(db_file) as ledger:
        ledger.stream_import("imp_1", data_file, chunk_size=25)

        # 99 valid records (1 malformed skipped)
        conn = ledger.get_conn()
        c = conn.execute("SELECT count(*) FROM magazine_records WHERE import_id = 'imp_1'")
        assert c.fetchone()[0] == 99

        # Test prefetch
        batch = ledger.prefetch(limit=10)
        assert len(batch) == 10
        for rec in batch:
            assert len(rec) == 3

        # Next prefetch should return remaining pending records
        batch2 = ledger.prefetch(limit=10)
        assert len(batch2) == 10
        # Ensure distinct records
        ids1 = {r[0] for r in batch}
        ids2 = {r[0] for r in batch2}
        assert ids1.isdisjoint(ids2)


def test_crash_recovery_and_deduplication(tmp_path: Path):
    db_file = tmp_path / "crash.sqlite3"
    data_file = tmp_path / "data_crash.jsonl"
    mag.generate_file(data_file, num_records=50)

    with mag.MagazineLedger(db_file) as ledger:
        with pytest.raises(RuntimeError, match="Simulated Crash"):
            ledger.stream_import("imp_crash", data_file, chunk_size=10, crash_after=25)

        # Verify partial import progress saved
        bytes_read, status = ledger.start_or_resume_import("imp_crash", str(data_file))
        assert bytes_read > 0
        assert status == "IMPORTING"

        # Resume import
        ledger.stream_import("imp_crash", data_file, chunk_size=10)

        # After resume, exactly 50 records exist without duplicates
        conn = ledger.get_conn()
        c = conn.execute("SELECT count(*) FROM magazine_records WHERE import_id = 'imp_crash'")
        assert c.fetchone()[0] == 50


def test_run_magazine_bench(tmp_path: Path):
    db_file = tmp_path / "bench.sqlite3"
    res = mag.run_magazine_bench(db_path=str(db_file))
    assert res["status"] == "PASS"
    assert res["prefetched_count"] == 10
    assert "peak_mb" in res
