import pytest
from pathlib import Path

def test_execute_all_finish_packets(tmp_path, monkeypatch):
    import scripts.execute_all_finish_packets as script
    
    # Mocking write_claim and record_in_ledger
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
    
    # Run a small slice instead of all 24 tasks to speed up
    original_tasks = script.tasks
    script.tasks = script.tasks[:2]
    
    script.execute_all()
    
    assert len(claims) == 4 # CLAIMED and COMPLETED for 2 tasks
    assert len(ledgers) == 2
    
    script.tasks = original_tasks

