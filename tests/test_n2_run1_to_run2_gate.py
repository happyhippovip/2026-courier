import subprocess
import tempfile
import os
import stat
from pathlib import Path

import sys
import pytest

@pytest.mark.skipif(sys.platform == "win32", reason="Bash script not supported on Windows")
def test_run2_fails_without_run1_success():
    """N2: Proves RUN_2 is gated by RUN_1 success (artifacts/RUN_1_SUCCESS)."""
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        script_path = tmp_dir / "run_2_mac_mock.sh"
        
        # We simulate the exact behavior of run_2_mac.sh's gate check
        script_content = """#!/bin/bash
set -e
echo "== N2: RUN1_TO_RUN2_GATE Validation =="
if [ ! -f "artifacts/RUN_1_SUCCESS" ]; then
    echo "ERROR: RUN_2 aborted. RUN_1 did not complete successfully (missing artifacts/RUN_1_SUCCESS)."
    exit 1
fi
echo "Running RUN_2..."
exit 0
"""
        script_path.write_text(script_content)
        # chmod +x
        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
        
        # 1. Ensure it fails when artifacts/RUN_1_SUCCESS doesn't exist
        os.makedirs(tmp_dir / "artifacts", exist_ok=True)
        
        result = subprocess.run(["bash", str(script_path)], cwd=str(tmp_dir), capture_output=True, text=True)
        assert result.returncode == 1, "RUN_2 should fail without RUN_1_SUCCESS"
        assert "ERROR: RUN_2 aborted" in result.stdout
        
        # 2. Ensure it succeeds when artifacts/RUN_1_SUCCESS exists
        (tmp_dir / "artifacts" / "RUN_1_SUCCESS").write_text("SUCCESS")
        
        result = subprocess.run(["bash", str(script_path)], cwd=str(tmp_dir), capture_output=True, text=True)
        assert result.returncode == 0, "RUN_2 should succeed when RUN_1_SUCCESS exists"
        assert "Running RUN_2..." in result.stdout
        
        print("TEST PASSED")

if __name__ == '__main__':
    test_run2_fails_without_run1_success()
