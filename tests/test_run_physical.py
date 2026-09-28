import pytest
from pathlib import Path
import json

def test_run_physical_success(tmp_path, monkeypatch):
    import scripts.run_physical as script
    
    monkeypatch.setattr(script, "check_resources", lambda *args, **kwargs: True)
    monkeypatch.setattr(script, "check_port_free", lambda *args, **kwargs: True)
    monkeypatch.setenv("COURIER_API_KEY", "test")
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "test")
    
    evidence_dir = tmp_path / "evidence"
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    
    central_state = {
        "goals": {
            "test_goal": {
                "workflow_plan": [
                    {"task_id": "process_a", "attempts": 1, "status": "COMPLETE"},
                    {"task_id": "process_b", "attempts": 1, "status": "COMPLETE"}
                ],
                "human_relay_count": 0
            }
        }
    }
    (state_dir / "central_state.json").write_text(json.dumps(central_state))
    
    class DummyResponse:
        def read(self):
            return json.dumps({"goal_id": "test_goal", "goal": {"status": "SUCCESS"}}).encode("utf-8")
            
    def dummy_urlopen(req, *args, **kwargs):
        return DummyResponse()
        
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", dummy_urlopen)
    
    import subprocess
    class DummyProcess:
        def __init__(self):
            self.pid = 9999
        def wait(self, timeout=None):
            pass
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: DummyProcess())
    
    exit_code = script.execute_run1("1234abcd", str(evidence_dir), 8081)
    
    assert exit_code == 0
    assert (evidence_dir / "run1_stdout.log").exists()
    assert (evidence_dir / "run1_exit_code.txt").read_text().strip() == "0"
    
    snapshot = json.loads((evidence_dir / "run1_state_snapshot.json").read_text())
    assert snapshot["final_status"] == "SUCCESS"
    assert snapshot["candidate_sha"] == "1234abcd"
    
    assert (evidence_dir / "run1_falsifiability_hash.txt").exists()
