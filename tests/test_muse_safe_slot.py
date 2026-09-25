"""Exercise the scoped data-home launcher without contacting a provider."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_safe_slot_scopes_data_home_and_restores_environment(tmp_path):
    shell = shutil.which("powershell.exe")
    if not shell:
        pytest.skip("Windows PowerShell required")
    launcher = Path(__file__).resolve().parents[1] / "scripts/windows_muse_wall/launch_safe_slot.ps1"
    assert launcher.is_file()
    data = tmp_path / "data home"
    work = tmp_path / "slot work"
    data.mkdir()
    work.mkdir()
    # Function stand-in captures the actual argument/environment contract.
    script = """
    function muse { [pscustomobject]@{Arguments=@($args); Data=$env:XDG_DATA_HOME} | ConvertTo-Json -Compress }
    $env:XDG_DATA_HOME='original-data-home'
    & $env:TEST_LAUNCHER -Workspace $env:TEST_WORK -DataHome $env:TEST_DATA
    if ($env:XDG_DATA_HOME -ne 'original-data-home') { throw 'Environment leaked' }
    """
    env = dict(os.environ, TEST_LAUNCHER=str(launcher), TEST_WORK=str(work), TEST_DATA=str(data))
    result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", script],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["Arguments"] == ["--disable-approval", "--workspace", str(work)]
    assert observed["Data"] == str(data)
