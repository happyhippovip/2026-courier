import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(os.name != "nt", reason="Windows specific test")
def test_uninstall_motor_service_ps1_syntax_and_dry_run():
    ps1_path = REPO_ROOT / "scripts" / "uninstall_motor_service.ps1"
    assert ps1_path.exists()

    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1_path),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0
    assert "Courier Motor Service Uninstaller" in proc.stdout
    assert "Courier Motor uninstallation complete" in proc.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows specific test")
def test_uninstall_verifier_service_ps1_syntax_and_dry_run():
    ps1_path = REPO_ROOT / "scripts" / "uninstall_verifier_service.ps1"
    assert ps1_path.exists()

    # Note: CourierVerifier task is actually registered on this system,
    # so we run syntax verification using AST parser to prevent unregistering live verifier!
    ast_check = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"& {{ $e = $null; [System.Management.Automation.Language.Parser]::ParseFile('{ps1_path}', [ref]$null, [ref]$e); if ($e.Count -eq 0) {{ 'PARSER_OK' }} else {{ $e }} }}",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert ast_check.returncode == 0
    assert "PARSER_OK" in ast_check.stdout
