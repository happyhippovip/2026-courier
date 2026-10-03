import subprocess
import sys
import json
import time
from pathlib import Path

def test_hub_dynamic_port_contract(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    contract_file = home / "run" / "hub.json"
    
    # We pass port 0 to allow OS selection, and write the contract to file
    proc = subprocess.Popen([
        sys.executable, "-m", "courier_hub",
        "--home", str(home),
        "--controller", "http://127.0.0.1:8765",
        "--port", "0",
        "--contract-file", str(contract_file)
    ])
    
    try:
        # Wait for contract file
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if contract_file.exists():
                break
            time.sleep(0.1)
            
        assert contract_file.exists(), "Hub did not write the contract file in time"
        
        contract = json.loads(contract_file.read_text())
        assert "port" in contract
        assert "url" in contract
        
        port = contract["port"]
        url = contract["url"]
        
        assert isinstance(port, int)
        assert port > 0
        assert url == f"http://127.0.0.1:{port}/"
        
        # Verify it's actually answering on that port
        import requests
        resp = requests.get(url + "hub/api/status")
        # Might return 503 because controller is fake, but we get an HTTP response
        assert resp.status_code in (200, 503)
        
    finally:
        proc.terminate()
        proc.wait(timeout=3)

