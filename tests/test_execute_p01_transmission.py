import json
import pytest
from pathlib import Path

from scripts import execute_p01_transmission


def test_transmit_p01_success(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    
    # Create mock path
    spec_path = Path("events/revenue-opportunities/market_intelligence/FINAL_P01_FOLLOWUP_SPEC.json")
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    
    spec = {
        "current_status": "WAITING_FOR_HUMAN",
        "message_fingerprint": "xyz123"
    }
    with open(spec_path, "w") as f:
        json.dump(spec, f)
        
    code = execute_p01_transmission.transmit_p01()
    captured = capsys.readouterr().out
        
    with open(spec_path, "r") as f:
        updated_spec = json.load(f)
        
    assert code != 0
    assert "Success: P-01 Follow-Up Transmitted" not in captured
    assert updated_spec["current_status"] == "WAITING_FOR_HUMAN"
    assert "transmitted_at" not in updated_spec


def test_transmit_p01_already_transmitted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    spec_path = Path("events/revenue-opportunities/market_intelligence/FINAL_P01_FOLLOWUP_SPEC.json")
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    
    spec = {
        "current_status": "TRANSMITTED_BY_CHIEF",
        "message_fingerprint": "xyz123"
    }
    with open(spec_path, "w") as f:
        json.dump(spec, f)
        
    execute_p01_transmission.transmit_p01()
        
    # File should remain unchanged
    with open(spec_path, "r") as f:
        updated_spec = json.load(f)
        
    assert updated_spec["current_status"] == "TRANSMITTED_BY_CHIEF"
    assert "transmitted_at" not in updated_spec


def test_main(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    spec_path = Path("events/revenue-opportunities/market_intelligence/FINAL_P01_FOLLOWUP_SPEC.json")
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    
    spec = {
        "current_status": "WAITING_FOR_HUMAN",
        "message_fingerprint": "abc999"
    }
    with open(spec_path, "w") as f:
        json.dump(spec, f)
        
    import runpy
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "execute_p01_transmission.py"), run_name="__main__")
    assert caught.value.code != 0
        
    with open(spec_path, "r") as f:
        updated_spec = json.load(f)
        
    assert updated_spec["current_status"] == "WAITING_FOR_HUMAN"
    assert "transmitted_at" not in updated_spec
