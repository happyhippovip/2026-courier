import json
import time
import pytest
from pathlib import Path
from unittest import mock

from scripts import execute_p01_transmission


def test_transmit_p01_success(tmp_path, monkeypatch):
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
        
    def mock_gmtime():
        # fixed time tuple
        return time.struct_time((2026, 9, 30, 12, 0, 0, 2, 273, 0))
        
    with mock.patch("time.gmtime", side_effect=mock_gmtime):
        execute_p01_transmission.transmit_p01()
        
    with open(spec_path, "r") as f:
        updated_spec = json.load(f)
        
    assert updated_spec["current_status"] == "TRANSMITTED_BY_CHIEF"
    assert updated_spec["transmitted_at"] == "2026-09-30T12:00:00+00:00"


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
    runpy.run_path("C:/Users/lol/2026-workspace/2026-courier/scripts/execute_p01_transmission.py", run_name="__main__")
        
    with open(spec_path, "r") as f:
        updated_spec = json.load(f)
        
    assert updated_spec["current_status"] == "TRANSMITTED_BY_CHIEF"
