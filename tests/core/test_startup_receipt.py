import pytest
import os
import sys
import json
from pathlib import Path
from courier_core.launcher import Launcher, StartupTimeoutError

def test_startup_failure_receipt(tmp_path):
    mock_server = tmp_path / "mock_core.py"
    mock_server.write_text("""
import sys
sys.stderr.write('Fatal error: missing config\\n')
sys.stderr.flush()
sys.exit(1)
""")
    
    old_pythonpath = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = f"{tmp_path}:{old_pythonpath}"
    
    launcher = Launcher(str(tmp_path), core_module="mock_core")
    
    try:
        launcher.start(timeout_s=5.0)
        assert False, "Should have raised LauncherError"
    except Exception as e:
        assert e.receipt is not None
        assert e.receipt.component == "controller"
        assert e.receipt.exit_code == 1
        assert e.receipt.stage == "port_binding"
        assert e.receipt.recoverability is False
        assert "Fatal error: missing config" in e.receipt.logs
        
        # Verify it was written to disk
        assert os.path.exists(e.receipt.evidence_path)
        with open(e.receipt.evidence_path, "r") as f:
            data = json.load(f)
            assert data["exit_code"] == 1
            assert data["recoverability"] is False
            assert "Fatal error: missing config" in data["logs"]
            
    finally:
        os.environ["PYTHONPATH"] = old_pythonpath
        launcher.stop()

def test_startup_timeout_receipt_recoverability(tmp_path):
    mock_server = tmp_path / "mock_core.py"
    mock_server.write_text("""
import sys, time
time.sleep(10)
""")
    
    old_pythonpath = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = f"{tmp_path}:{old_pythonpath}"
    
    launcher = Launcher(str(tmp_path), core_module="mock_core")
    
    try:
        launcher.start(timeout_s=0.5)
        assert False, "Should have raised StartupTimeoutError"
    except Exception as e:
        assert isinstance(e, StartupTimeoutError)
        assert e.receipt is not None
        assert e.receipt.recoverability is True
        assert e.receipt.stage == "port_binding"
    finally:
        os.environ["PYTHONPATH"] = old_pythonpath
        launcher.stop()
