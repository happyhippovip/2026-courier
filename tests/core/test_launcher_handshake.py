import pytest
from pathlib import Path
from courier_core.launcher import Launcher, LauncherError
import tempfile
import urllib.request
import json

def test_deterministic_handshake(tmp_path):
    launcher = Launcher(str(tmp_path))
    try:
        port, token = launcher.start()
        assert port > 0
        assert len(token) > 0
        
        # Verify it actually works after READY
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/health",
            headers={"X-Courier-Token": token}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
            assert data["mode"] == "normal"
    finally:
        launcher.stop()
