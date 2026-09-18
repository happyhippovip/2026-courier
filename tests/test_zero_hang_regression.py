import pytest
import subprocess
import time
import sys
from pathlib import Path

def test_subprocess_run_timeout_regression(tmp_path):
    """
    Ensures that our architecture handles stuck processes by imposing strict timeouts.
    If a regression removes timeouts from subprocess calls, this test will hang forever.
    """
    script_path = tmp_path / "stuck.py"
    script_path.write_text("import time\ntime.sleep(60)\n")
    
    start = time.time()
    try:
        subprocess.run(
            [sys.executable, str(script_path)],
            timeout=1,
            check=True
        )
        assert False, "Should have timed out"
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        assert False, f"Unexpected exception: {e}"
        
    duration = time.time() - start
    assert duration < 5, "Timeout regression: stuck process took too long to kill!"
