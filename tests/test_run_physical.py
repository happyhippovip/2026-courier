import pytest
from pathlib import Path
import json
import os

def test_run_physical_success(tmp_path, monkeypatch):
    import scripts.run_physical as script
    
    # Mock system checks
    monkeypatch.setattr(script, "check_resources", lambda *args, **kwargs: True)
    monkeypatch.setattr(script, "check_port_free", lambda *args, **kwargs: True)
    
    evidence_dir = tmp_path / "evidence"
    
    # Execute run1
    exit_code = script.execute_run("1234abcd", str(evidence_dir), 8081)
    
    assert exit_code == 0
    assert (evidence_dir / "run1_stdout.log").exists()
    assert (evidence_dir / "run1_exit_code.txt").read_text().strip() == "0"
    
    snapshot = json.loads((evidence_dir / "run1_state_snapshot.json").read_text())
    assert snapshot["final_status"] == "SUCCESS"
    assert snapshot["candidate_sha"] == "1234abcd"
    
    # Verify hash exists
    assert (evidence_dir / "run1_falsifiability_hash.txt").exists()

