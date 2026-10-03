import pytest
import os
import sys
from pathlib import Path
from courier_core.launcher import Launcher, StartupTimeoutError

def test_startup_timeout_preserves_evidence(tmp_path):
    # We will simulate a slow server by pointing to a mock core module that just sleeps and prints to stderr
    mock_server = tmp_path / "mock_core.py"
    mock_server.write_text("""
import sys, time
sys.stderr.write('Mock server booting up...\\n')
sys.stderr.flush()
time.sleep(10)
""")
    
    # We add tmp_path to sys.path so the mock_core can be run via -m
    old_pythonpath = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = f"{tmp_path}:{old_pythonpath}"
    
    launcher = Launcher(str(tmp_path), core_module="mock_core")
    
    try:
        with pytest.raises(StartupTimeoutError) as exc_info:
            launcher.start(timeout_s=0.5)
            
        err = exc_info.value
        assert "Mock server booting up" in err.stderr_output, "Diagnostic evidence was not preserved!"
        assert "Startup handshake timed out" in str(err)
    finally:
        os.environ["PYTHONPATH"] = old_pythonpath
        launcher.stop()

