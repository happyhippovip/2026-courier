import os
import zipfile
import json
from pathlib import Path
import tempfile
import pytest

from scripts.courier_doctor import export_diagnostics, get_app_data_dir

def test_diagnostics_bundle_redacts_api_key(monkeypatch, tmp_path):
    # Setup mock data directory
    mock_app_data = tmp_path / "mock_app_data"
    mock_app_data.mkdir()
    
    # Mock get_app_data_dir to return our mock dir
    monkeypatch.setattr("scripts.courier_doctor.get_app_data_dir", lambda: mock_app_data)
    
    # Create mock config with API key
    secret_key = "secret_api_key_12345"
    config_path = mock_app_data / "config.json"
    with open(config_path, "w") as f:
        json.dump({"COURIER_API_KEY": secret_key, "COURIER_SERVER": "http://testserver"}, f)
        
    # Create mock state and logs containing the API key
    state_dir = mock_app_data / "state"
    state_dir.mkdir()
    with open(state_dir / "current_task.json", "w") as f:
        json.dump({"auth": f"Bearer {secret_key}", "worker_phase": "STARTED"}, f)
        
    log_dir = mock_app_data / "logs"
    log_dir.mkdir()
    with open(log_dir / "daemon.log", "w") as f:
        f.write(f"Connecting with {secret_key}...")
        
    # Ensure environment doesn't override with something else
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    
    # Run export
    bundle_path = tmp_path / "diagnostics.zip"
    export_diagnostics(bundle_path)
    
    # Verify bundle contents
    assert bundle_path.exists()
    
    with zipfile.ZipFile(bundle_path, "r") as zf:
        for name in zf.namelist():
            content = zf.read(name).decode("utf-8")
            assert secret_key not in content, f"Secret leaked in {name}"
            assert "***REDACTED_API_KEY***" in content, f"Secret not redacted in {name}"
