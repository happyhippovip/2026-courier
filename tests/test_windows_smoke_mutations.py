"""Hardened Mutation Tests for Windows Worker Package and Smoke Verifier.

Tests that all intentional mutations (missing policy, truncated binaries,
stripped security guards, invalid JSON, removed local_shell) are strictly
detected and rejected by the smoke verification suite.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = ROOT / "scripts" / "windows_worker" / "smoke_package.ps1"


@pytest.fixture
def mock_valid_package(tmp_path: Path) -> Path:
    """Create a fully valid mock package directory matching the expected structure."""
    pkg = tmp_path / "dist"
    pkg.mkdir()

    # Core binaries & scripts (> 10 bytes)
    (pkg / "Courier.exe").write_bytes(b"MZ" + b"\x90" * 100)
    (pkg / "daemon.py").write_text("#!/usr/bin/env python\nprint('daemon')\n", encoding="utf-8")
    (pkg / "bootstrap.ps1").write_text("# Bootstrap script\nWrite-Host 'boot'\n", encoding="utf-8")
    (pkg / "install.ps1").write_text("# Install script\nWrite-Host 'install'\n", encoding="utf-8")
    (pkg / "uninstall.ps1").write_text("# Uninstall script\nWrite-Host 'uninstall'\n", encoding="utf-8")

    # Worker package
    worker_dir = pkg / "courier_worker"
    worker_dir.mkdir()
    (worker_dir / "host.py").write_text("# host\nclass Host: pass\n", encoding="utf-8")
    (worker_dir / "service.py").write_text("# service\nclass Service: pass\n", encoding="utf-8")

    # Adapters with hardened local_shell
    adapters_dir = pkg / "adapters"
    adapters_dir.mkdir()
    (adapters_dir / "local_shell.py").write_text(
        "# Hardened local_shell\n"
        "if '\\x00' in cmd: raise ValueError('NUL')\n"
        "command_blocklist = ['rmdir', 'format']\n"
        "if cmd in command_blocklist: return 'blocked'\n",
        encoding="utf-8",
    )

    # Scripts directory with resource policy
    scripts_dir = pkg / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "resource_policy.py").write_text(
        "# Resource policy with CostGate\n"
        "UNKNOWN_COST = 'BLOCK'\n"
        "def check_cost(): return 'CostGate_ENFORCED'\n",
        encoding="utf-8",
    )

    # Events policy JSON
    policies_dir = pkg / "events" / "policies"
    policies_dir.mkdir(parents=True)
    (policies_dir / "resource_policy.json").write_text(
        json.dumps({"max_spend": 0.00, "policy_version": "2.0"}),
        encoding="utf-8",
    )

    return pkg


def _run_smoke(pkg_dir: Path) -> tuple[int, str]:
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(SMOKE_SCRIPT),
        "-PackageDir", str(pkg_dir),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = (proc.stdout or b"").decode("utf-8", errors="replace") + " " + (proc.stderr or b"").decode("utf-8", errors="replace")
    normalized = " ".join(out.split())
    return proc.returncode, normalized


def test_valid_package_passes_smoke(mock_valid_package: Path):
    rc, out = _run_smoke(mock_valid_package)
    assert rc == 0, f"Output was: {out}"
    assert "SMOKE_PASS" in out


def test_mutation_missing_courier_exe(mock_valid_package: Path):
    (mock_valid_package / "Courier.exe").unlink()
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "Courier.exe" in out


def test_mutation_missing_resource_policy(mock_valid_package: Path):
    (mock_valid_package / "scripts" / "resource_policy.py").unlink()
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "resource_policy.py" in out


def test_mutation_corrupt_policy_json(mock_valid_package: Path):
    (mock_valid_package / "events" / "policies" / "resource_policy.json").write_text(
        "{INVALID_JSON_CORRUPT: true,", encoding="utf-8"
    )
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "resource_policy.json" in out


def test_mutation_missing_local_shell(mock_valid_package: Path):
    (mock_valid_package / "adapters" / "local_shell.py").unlink()
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "local_shell.py" in out


def test_mutation_truncated_binary(mock_valid_package: Path):
    (mock_valid_package / "Courier.exe").write_bytes(b"")
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "Truncated" in out or "empty" in out


def test_mutation_stripped_nul_guard_in_local_shell(mock_valid_package: Path):
    (mock_valid_package / "adapters" / "local_shell.py").write_text(
        "# Insecure local shell\ndef run(cmd): os.system(cmd)\n", encoding="utf-8"
    )
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "local_shell.py is missing" in out


def test_mutation_stripped_costgate_in_policy(mock_valid_package: Path):
    (mock_valid_package / "scripts" / "resource_policy.py").write_text(
        "# Empty policy\npass\n", encoding="utf-8"
    )
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "resource_policy.py is missing CostGate" in out


def test_mutation_missing_entire_package_dir(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist"
    rc, out = _run_smoke(non_existent)
    assert rc != 0
    assert "does not exist" in out
