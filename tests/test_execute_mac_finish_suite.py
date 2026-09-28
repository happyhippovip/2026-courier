import pytest
from pathlib import Path
import json

def test_execute_mac_finish_suite(tmp_path, monkeypatch):
    import scripts.execute_mac_finish_suite as script
    
    claims_dir = tmp_path / "claims"
    results_dir = tmp_path / "results"
    ledger_db = tmp_path / "ledger.db"
    ledger_jsonl = tmp_path / "ledger.jsonl"
    
    claims_dir.mkdir()
    results_dir.mkdir()
    
    monkeypatch.setattr(script, "CLAIMS_DIR", str(claims_dir))
    monkeypatch.setattr(script, "RESULTS_DIR", str(results_dir))
    monkeypatch.setattr(script, "LEDGER_DB_PATH", str(ledger_db))
    monkeypatch.setattr(script, "LEDGER_JSONL_PATH", str(ledger_jsonl))
    
    import sqlite3
    conn = sqlite3.connect(str(ledger_db))
    conn.execute('''CREATE TABLE ledger (id INTEGER PRIMARY KEY, task_id TEXT, status TEXT, evidence_path TEXT, fingerprint TEXT, prev_hash TEXT, block_hash TEXT)''')
    conn.commit()
    conn.close()
    
    # Test write_claim
    script.write_claim("test_task", "CLAIMED")
    claim_file = claims_dir / "test_task.claim.json"
    assert claim_file.exists()
    
    # Test record_in_ledger
    script.record_in_ledger("test_task", "COMPLETED", "test_path", "test_fingerprint")
    assert ledger_jsonl.exists()
    with open(str(ledger_jsonl), "r") as f:
        data = json.loads(f.read().strip())
        assert data["TASK_ID"] == "test_task"

