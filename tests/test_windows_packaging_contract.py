"""Audit contract for Windows Worker R1 packaging (build_package.ps1).

Verifies P0-B requirements:
- Policy and CostGate modules are explicitly packaged.
- Pre-flight checks refuse build when required components are missing.
- No insecure default policies or unverified paid active entries are bundled.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_PS1 = ROOT / "scripts" / "windows_worker" / "build_package.ps1"


def test_build_package_script_has_preflight_refusal():
    assert BUILD_PS1.is_file()
    text = BUILD_PS1.read_text(encoding="utf-8")

    # Pre-flight refusal check
    assert "BUILD REFUSED" in text
    assert "$requiredPaths" in text
    for req in (
        "Courier.exe",
        "install.ps1",
        "uninstall.ps1",
        "courier_core",
        "courier_hub",
        "courier_runtime",
        "courier_worker",
        "scripts\\resource_policy.py",
        "events\\policies\\resource_policy.json",
    ):
        assert req in text, f"Missing required path check for {req}"


def test_build_package_script_bundles_policy_and_runtime():
    text = BUILD_PS1.read_text(encoding="utf-8")

    # Ensure courier_runtime is bundled
    assert 'Copy-Item -Recurse "$projectRoot\\courier_runtime" -Destination "$OutDir\\courier_runtime"' in text

    # Ensure scripts/resource_policy.py is bundled
    assert 'Copy-Item "$projectRoot\\scripts\\resource_policy.py" -Destination "$OutDir\\scripts\\resource_policy.py"' in text

    # Ensure events/policies/resource_policy.json is bundled
    assert 'Copy-Item "$projectRoot\\events\\policies\\resource_policy.json" -Destination "$OutDir\\events\\policies\\resource_policy.json"' in text


def test_build_package_pins_embedded_python_hash():
    text = BUILD_PS1.read_text(encoding="utf-8")
    assert "a86a2e28870967745d255cc597d1e4d19ae79e65e927cdc324baa0256202231c" in text
    assert "Get-FileHash -Algorithm SHA256" in text
    assert "BUILD REFUSED: embedded Python SHA-256 mismatch" in text
    assert "exit 1" in text


def test_bundled_policy_is_fail_closed():
    from scripts.resource_policy import ResourcePolicyManager

    # 1. Fallback policy when file is missing must be completely empty (no active resources)
    fallback = ResourcePolicyManager._FAIL_CLOSED_POLICY
    assert fallback["active_paid_resources"] == {}
    assert fallback["_policy_invalid"] is True

    # 2. Canonical policy file on disk must enforce strict invariants
    policy_path = ROOT / "events" / "policies" / "resource_policy.json"
    assert policy_path.is_file()
    data = json.loads(policy_path.read_text(encoding="utf-8"))

    inv = data.get("operating_invariants", {})
    assert inv.get("allow_auto_capacity_expansion") is False
    assert inv.get("require_human_gate_for_tier_change") is True
    assert inv.get("max_autonomous_iterations_per_task") == 1

    # Unauthorized resources must forbid spend
    unauth = data.get("unauthorized_resources", {})
    for res_name, res_info in unauth.items():
        assert res_info.get("spend_allowed") is False
