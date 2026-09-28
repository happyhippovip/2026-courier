import pytest
import json
from pathlib import Path

def test_transmit_p01(tmp_path, monkeypatch):
    import scripts.execute_p01_transmission as script
    
    spec_path = tmp_path / "FINAL_P01_FOLLOWUP_SPEC.json"
    spec_path.write_text(json.dumps({
        "current_status": "WAITING_FOR_HUMAN",
        "message_fingerprint": "abc"
    }))
    
    # Mock Path to point to tmp_path file
    def mock_path(*args, **kwargs):
        if args[0] == "events/revenue-opportunities/market_intelligence/FINAL_P01_FOLLOWUP_SPEC.json":
            return spec_path
        return Path(*args, **kwargs)
        
    monkeypatch.setattr(script, "Path", mock_path)
    
    script.transmit_p01()
    
    updated = json.loads(spec_path.read_text())
    assert updated["current_status"] == "TRANSMITTED_BY_CHIEF"
    assert "transmitted_at" in updated

def test_transmit_p01_already_transmitted(tmp_path, monkeypatch, capsys):
    import scripts.execute_p01_transmission as script
    
    spec_path = tmp_path / "FINAL_P01_FOLLOWUP_SPEC.json"
    spec_path.write_text(json.dumps({
        "current_status": "TRANSMITTED_BY_CHIEF",
        "message_fingerprint": "abc"
    }))
    
    def mock_path(*args, **kwargs):
        if args[0] == "events/revenue-opportunities/market_intelligence/FINAL_P01_FOLLOWUP_SPEC.json":
            return spec_path
        return Path(*args, **kwargs)
        
    monkeypatch.setattr(script, "Path", mock_path)
    
    script.transmit_p01()
    
    out, _ = capsys.readouterr()
    assert "already in status" in out

