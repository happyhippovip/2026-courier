import pytest
from pathlib import Path
import json

def test_execute_hard_no_idle50_suite(tmp_path, monkeypatch):
    import scripts.execute_hard_no_idle50_suite as script
    
    claims_dir = tmp_path / "claims"
    results_dir = tmp_path / "results"
    deliv_dir = tmp_path / "deliv"
    ledger_db = tmp_path / "ledger.db"
    ledger_jsonl = tmp_path / "ledger.jsonl"
    
    claims_dir.mkdir()
    results_dir.mkdir()
    deliv_dir.mkdir()
    
    monkeypatch.setattr(script, "CLAIMS_DIR", str(claims_dir))
    monkeypatch.setattr(script, "RESULTS_DIR", str(results_dir))
    monkeypatch.setattr(script, "DELIVERABLES_DIR", str(deliv_dir))
    monkeypatch.setattr(script, "LEDGER_DB_PATH", str(ledger_db))
    monkeypatch.setattr(script, "LEDGER_JSONL_PATH", str(ledger_jsonl))
    monkeypatch.setattr(script, "WORKSPACE_ROOT", str(tmp_path))
    
    import sqlite3
    conn = sqlite3.connect(str(ledger_db))
    conn.execute('''CREATE TABLE ledger (id INTEGER PRIMARY KEY, task_id TEXT, status TEXT, evidence_path TEXT, fingerprint TEXT, prev_hash TEXT, block_hash TEXT)''')
    conn.commit()
    conn.close()
    
    original_tasks = script.tasks
    script.tasks = script.tasks[:2]
    
    script.main()
    
    assert (claims_dir / "HNI_01_RUNTIME_INVARIANT_AUDIT.claim.json").exists()
    assert (results_dir / "HNI_01_RUNTIME_INVARIANT_AUDIT_result.md").exists()
    assert (deliv_dir / "HNI_01_RUNTIME_INVARIANT_AUDIT.md").exists()
    
    assert ledger_jsonl.exists()
    
    script.tasks = original_tasks

