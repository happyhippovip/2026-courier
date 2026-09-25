import pytest
import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.magazine import MagazineLedger, generate_file

@pytest.fixture
def ledger(tmp_path):
    db_path = tmp_path / "test_magazine.sqlite3"
    ledger = MagazineLedger(str(db_path))
    yield ledger

def test_stream_import_basic(ledger, tmp_path):
    file_path = tmp_path / "test_10.jsonl"
    generate_file(str(file_path), 10)
    
    ledger.stream_import("import_1", str(file_path), chunk_size=5)
    
    with ledger.get_conn() as conn:
        c = conn.execute("SELECT count(*) FROM magazine_records WHERE import_id='import_1'")
        count = c.fetchone()[0]
        assert count == 10

def test_stream_import_crash_recovery(ledger, tmp_path):
    file_path = tmp_path / "test_crash.jsonl"
    generate_file(str(file_path), 100)
    
    with pytest.raises(RuntimeError) as exc:
        ledger.stream_import("import_crash", str(file_path), chunk_size=10, crash_after=25)
        
    assert "Simulated Crash" in str(exc.value)
    
    with ledger.get_conn() as conn:
        c = conn.execute("SELECT count(*) FROM magazine_records WHERE import_id='import_crash'")
        count = c.fetchone()[0]
        assert count == 25 # 2 chunks of 10
        
    # Resume import
    ledger.stream_import("import_crash", str(file_path), chunk_size=10)
    
    with ledger.get_conn() as conn:
        c = conn.execute("SELECT count(*) FROM magazine_records WHERE import_id='import_crash'")
        count = c.fetchone()[0]
        assert count == 100

def test_prefetch(ledger, tmp_path):
    file_path = tmp_path / "test_prefetch.jsonl"
    generate_file(str(file_path), 20)
    
    ledger.stream_import("import_prefetch", str(file_path), chunk_size=10)
    
    batch = ledger.prefetch(limit=5)
    assert len(batch) == 5
    
    batch2 = ledger.prefetch(limit=10)
    assert len(batch2) == 10
    
    with ledger.get_conn() as conn:
        c = conn.execute("SELECT count(*) FROM magazine_records WHERE status='ACTIVE'")
        count = c.fetchone()[0]
        assert count == 15

def test_malformed_json(ledger, tmp_path):
    file_path = tmp_path / "test_malformed.jsonl"
    generate_file(str(file_path), 10, malformed_at=5)
    
    ledger.stream_import("import_malformed", str(file_path), chunk_size=5)
    
    with ledger.get_conn() as conn:
        c = conn.execute("SELECT count(*) FROM magazine_records WHERE import_id='import_malformed'")
        count = c.fetchone()[0]
        assert count == 9 # 10 total - 1 malformed

