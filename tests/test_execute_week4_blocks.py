import pytest
from pathlib import Path

def test_execute_week4_blocks(tmp_path, monkeypatch):
    import scripts.execute_week4_blocks as script
    
    claims = []
    def mock_write_claim(task_id, status):
        claims.append((task_id, status))
        return None, True
        
    ledgers = []
    def mock_record_in_ledger(task_id, status, deliv, fingerprint):
        ledgers.append(task_id)
        
    monkeypatch.setattr(script, "write_claim", mock_write_claim)
    monkeypatch.setattr(script, "record_in_ledger", mock_record_in_ledger)
    
    deliv_dir = tmp_path / "deliv"
    res_dir = tmp_path / "res"
    deliv_dir.mkdir()
    res_dir.mkdir()
    
    monkeypatch.setattr(script, "DELIVERABLES_DIR", str(deliv_dir))
    monkeypatch.setattr(script, "RESULTS_DIR", str(res_dir))
    monkeypatch.setattr(script, "WORKSPACE_ROOT", str(tmp_path))
    
    original_tasks = script.week4_blocks
    script.week4_blocks = script.week4_blocks[:2]
    
    script.execute_all()
    
    assert len(claims) == 4
    assert len(ledgers) == 2
    
    script.week4_blocks = original_tasks

