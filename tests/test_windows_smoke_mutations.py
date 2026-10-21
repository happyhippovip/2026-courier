"""Hardened Mutation Tests for Windows Worker Package and Smoke Verifier.

Tests that all intentional mutations (missing policy, truncated binaries,
stripped security guards, invalid JSON, removed local_shell, manifest corruption,
and hash/size tampering) are strictly detected and rejected by the smoke
verification suite.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = ROOT / "scripts" / "windows_worker" / "smoke_package.ps1"


def _generate_manifest_for_pkg(pkg: Path) -> dict:
    files_dict = {}
    for p in sorted(pkg.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel_path = str(p.relative_to(pkg)).replace("\\", "/")
            data = p.read_bytes()
            sha256 = hashlib.sha256(data).hexdigest().upper()
            files_dict[rel_path] = {
                "size": len(data),
                "sha256": sha256
            }
    manifest = {
        "manifest_version": "1.0",
        "algorithm": "SHA256",
        "package_name": "CourierWorker-Windows",
        "file_count": len(files_dict),
        "files": files_dict
    }
    (pkg / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


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
    (pkg / "install_service.ps1").write_text("# Install service script\nWrite-Host 'install_service'\n", encoding="utf-8")
    (pkg / "uninstall.ps1").write_text("# Uninstall script\nWrite-Host 'uninstall'\n", encoding="utf-8")
    (pkg / "status.bat").write_text("@echo off\r\necho status\r\n", encoding="utf-8")
    (pkg / "stop.bat").write_text("@echo off\r\necho stop\r\n", encoding="utf-8")

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

    # Generate valid cryptographic manifest
    _generate_manifest_for_pkg(pkg)

    return pkg


def _run_smoke(pkg_dir: Path, require_manifest: bool = False) -> tuple[int, str]:
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(SMOKE_SCRIPT),
        "-PackageDir", str(pkg_dir),
    ]
    if require_manifest:
        cmd.append("-RequireManifest")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = (proc.stdout or b"").decode("utf-8", errors="replace") + " " + (proc.stderr or b"").decode("utf-8", errors="replace")
    normalized = " ".join(out.split())
    return proc.returncode, normalized


def test_valid_package_passes_smoke(mock_valid_package: Path):
    rc, out = _run_smoke(mock_valid_package, require_manifest=True)
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
    # regenerate manifest so smoke fails on the code guard, not the hash
    _generate_manifest_for_pkg(mock_valid_package)
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "local_shell.py is missing" in out


def test_mutation_stripped_costgate_in_policy(mock_valid_package: Path):
    (mock_valid_package / "scripts" / "resource_policy.py").write_text(
        "# Empty policy\npass\n", encoding="utf-8"
    )
    # regenerate manifest so smoke fails on the policy guard, not the hash
    _generate_manifest_for_pkg(mock_valid_package)
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "resource_policy.py is missing CostGate" in out


def test_mutation_missing_entire_package_dir(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist"
    rc, out = _run_smoke(non_existent)
    assert rc != 0
    assert "does not exist" in out


# --- Cryptographic Manifest (W04 / GB-PKG-04) Mutations ---

def test_mutation_corrupt_manifest_json(mock_valid_package: Path):
    (mock_valid_package / "manifest.json").write_text("{CORRUPT_JSON: true,", encoding="utf-8")
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "manifest.json is corrupt" in out


def test_mutation_manifest_missing_files_dictionary(mock_valid_package: Path):
    (mock_valid_package / "manifest.json").write_text(json.dumps({"manifest_version": "1.0"}), encoding="utf-8")
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "missing 'files' dictionary" in out


def test_mutation_tampered_binary_hash_mismatch(mock_valid_package: Path):
    # Alter bytes of Courier.exe without updating manifest
    (mock_valid_package / "Courier.exe").write_bytes(b"MZ" + b"\xff" * 100)
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "Cryptographic checksum failures" in out
    assert "Courier.exe" in out


def test_mutation_tampered_file_size_mismatch(mock_valid_package: Path):
    # Append content to daemon.py to change size
    current = (mock_valid_package / "daemon.py").read_text(encoding="utf-8")
    (mock_valid_package / "daemon.py").write_text(current + "# extra content\n", encoding="utf-8")
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "Manifest file size discrepancies" in out or "Cryptographic checksum failures" in out


def test_mutation_manifest_file_missing_from_disk(mock_valid_package: Path):
    # Manifest declares a file that doesn't exist
    manifest_data = json.loads((mock_valid_package / "manifest.json").read_text(encoding="utf-8"))
    manifest_data["files"]["ghost_file.dll"] = {"size": 100, "sha256": "ABCD1234"}
    (mock_valid_package / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "Files in manifest missing from disk" in out
    assert "ghost_file.dll" in out


def test_mutation_require_manifest_fails_when_manifest_missing(mock_valid_package: Path):
    (mock_valid_package / "manifest.json").unlink()
    rc, out = _run_smoke(mock_valid_package, require_manifest=True)
    assert rc != 0
    assert "Required manifest.json is missing" in out


# --- Mandatory Policy Bundling & Governance (W05 / GB-PKG-05) Mutations ---

def test_mutation_policy_missing_version_specification(mock_valid_package: Path):
    (mock_valid_package / "events" / "policies" / "resource_policy.json").write_text(
        json.dumps({"max_spend": 0.00}), encoding="utf-8"
    )
    _generate_manifest_for_pkg(mock_valid_package)
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "missing required version specification" in out


def test_mutation_policy_missing_mandatory_invariants(mock_valid_package: Path):
    (mock_valid_package / "events" / "policies" / "resource_policy.json").write_text(
        json.dumps({"policy_version": "2.0"}), encoding="utf-8"
    )
    _generate_manifest_for_pkg(mock_valid_package)
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "missing mandatory governance invariants" in out


def test_mutation_policy_tampered_nonzero_spend(mock_valid_package: Path):
    (mock_valid_package / "events" / "policies" / "resource_policy.json").write_text(
        json.dumps({"policy_version": "2.0", "max_spend": 5.00}), encoding="utf-8"
    )
    _generate_manifest_for_pkg(mock_valid_package)
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "violates autonomous spend limit" in out


def test_mutation_policy_tampered_human_gate_disabled(mock_valid_package: Path):
    (mock_valid_package / "events" / "policies" / "resource_policy.json").write_text(
        json.dumps({
            "schema_version": "2026.08.30-policy-v1",
            "operating_invariants": {
                "require_human_gate_for_spend": False
            }
        }),
        encoding="utf-8"
    )
    _generate_manifest_for_pkg(mock_valid_package)
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "violates spend invariant" in out


def test_mutation_missing_install_service_script(mock_valid_package: Path):
    (mock_valid_package / "install_service.ps1").unlink()
    _generate_manifest_for_pkg(mock_valid_package)
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "Missing required package files: install_service.ps1" in out


def test_mutation_missing_status_lifecycle_script(mock_valid_package: Path):
    (mock_valid_package / "status.bat").unlink()
    _generate_manifest_for_pkg(mock_valid_package)
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "Missing required package files: status.bat" in out


def test_mutation_missing_stop_lifecycle_script(mock_valid_package: Path):
    (mock_valid_package / "stop.bat").unlink()
    _generate_manifest_for_pkg(mock_valid_package)
    rc, out = _run_smoke(mock_valid_package)
    assert rc != 0
    assert "Missing required package files: stop.bat" in out
