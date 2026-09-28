import os
import json
import uuid
import tempfile
from pathlib import Path
import subprocess

def test_intake_dispatcher_uses_correct_state_file(monkeypatch):
    import scripts.intake_dispatcher as dispatcher
    
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        state_file = tmp / "server" / "state" / "central_state.json"
        state_file.parent.mkdir(parents=True)
        monkeypatch.setenv("COURIER_STATE_FILE", str(state_file))
        
        intake_file = tmp / "intake.json"
        intake_file.write_text(json.dumps({
            "target_owner": "test",
            "target_repo": "repo",
            "target_sha": "abc",
            "customer_reference": "ref-123"
        }))
        
        # mock subprocess.run for gh workflow run
        def mock_run(cmd, *args, **kwargs):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="12345")
            
        monkeypatch.setattr(subprocess, "run", mock_run)
        
        # Dispatch it
        dispatcher.dispatch_intake(str(intake_file))
        
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert len(state["tasks"]) == 1
