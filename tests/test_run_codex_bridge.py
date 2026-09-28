import pytest
from pathlib import Path
import json

def test_run_chief_review_router_pass(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as script
    
    # Mock DECISIONS_DIR
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    monkeypatch.setattr(script, "DECISIONS_DIR", decisions_dir)
    
    res_file = tmp_path / "result.json"
    res_file.write_text(json.dumps({
        "correlation_id": "c-1",
        "payload": {
            "verdict": "PASS"
        }
    }))
    
    decision = script.run_chief_review_router("t-1", res_file)
    
    assert decision["verdict"] == "ACCEPTED"
    assert decision["action"] == "AUTO_APPROVE_SAFE_RESULT"
    
    decision_file = decisions_dir / "t-1-chief-decision.json"
    assert decision_file.exists()
    assert json.loads(decision_file.read_text())["verdict"] == "ACCEPTED"

def test_run_chief_review_router_needs_fix(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as script
    
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    monkeypatch.setattr(script, "DECISIONS_DIR", decisions_dir)
    
    res_file = tmp_path / "result.json"
    res_file.write_text(json.dumps({
        "correlation_id": "c-1",
        "payload": {
            "verdict": "NEEDS_FIX"
        }
    }))
    
    decision = script.run_chief_review_router("t-1", res_file)
    
    assert decision["verdict"] == "NEEDS_FIX"
    assert decision["action"] == "QUEUE_SCOPED_REPAIR_TASK"

def test_run_chief_review_router_human(tmp_path, monkeypatch):
    import scripts.run_codex_bridge as script
    
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    monkeypatch.setattr(script, "DECISIONS_DIR", decisions_dir)
    
    res_file = tmp_path / "result.json"
    res_file.write_text(json.dumps({
        "correlation_id": "c-1",
        "payload": {
            "verdict": "SOMETHING_ELSE"
        }
    }))
    
    decision = script.run_chief_review_router("t-1", res_file)
    
    assert decision["verdict"] == "HUMAN_APPROVAL_REQUIRED"
    assert decision["action"] == "STOP_AT_HUMAN_GATE"

