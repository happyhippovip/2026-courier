#!/usr/bin/env python3
"""Tests for scripts/entitlement_boundary.py."""

import json
from pathlib import Path
import pytest
import scripts.entitlement_boundary as eb


def test_default_entitlements(tmp_path: Path):
    non_existent = tmp_path / "non_existent.json"
    ents = eb.load_entitlements(license_path=non_existent)
    assert ents["tier"] == "COMMUNITY"
    assert ents["max_concurrent_tasks"] == 2
    assert "local_execution" in ents["features"]


def test_load_custom_license(tmp_path: Path):
    lic_file = tmp_path / "custom_license.json"
    lic_data = {
        "entitlements": {
            "tier": "ENTERPRISE",
            "max_concurrent_tasks": 16,
            "features": ["local_execution", "cloud_bursting", "audit_logging"],
        }
    }
    lic_file.write_text(json.dumps(lic_data), encoding="utf-8")

    ents = eb.load_entitlements(license_path=lic_file)
    assert ents["tier"] == "ENTERPRISE"
    assert ents["max_concurrent_tasks"] == 16
    assert "cloud_bursting" in ents["features"]


def test_invalid_json_fallback(tmp_path: Path):
    bad_lic = tmp_path / "broken.json"
    bad_lic.write_text("NOT_JSON_DATA", encoding="utf-8")

    ents = eb.load_entitlements(license_path=bad_lic)
    assert ents["tier"] == "COMMUNITY"
    assert ents["max_concurrent_tasks"] == 2


def test_check_capability(tmp_path: Path):
    lic_file = tmp_path / "license.json"
    lic_file.write_text(json.dumps({
        "entitlements": {
            "tier": "PRO",
            "max_concurrent_tasks": 4,
            "features": ["local_execution", "advanced_analytics"],
        }
    }), encoding="utf-8")

    assert eb.check_capability("advanced_analytics", license_path=lic_file) is True
    assert eb.check_capability("cloud_bursting", license_path=lic_file) is False


def test_get_task_limit(tmp_path: Path):
    lic_file = tmp_path / "license.json"
    lic_file.write_text(json.dumps({
        "entitlements": {
            "tier": "TEAM",
            "max_concurrent_tasks": 8,
            "features": ["local_execution"],
        }
    }), encoding="utf-8")

    assert eb.get_task_limit(license_path=lic_file) == 8


def test_env_var_override(tmp_path: Path, monkeypatch):
    lic_file = tmp_path / "env_license.json"
    lic_file.write_text(json.dumps({
        "entitlements": {
            "tier": "ENV_OVERRIDE",
            "max_concurrent_tasks": 10,
            "features": ["env_feature"],
        }
    }), encoding="utf-8")

    monkeypatch.setenv("COURIER_LICENSE_PATH", str(lic_file))
    ents = eb.load_entitlements()
    assert ents["tier"] == "ENV_OVERRIDE"
    assert ents["max_concurrent_tasks"] == 10


def test_cli_check_capability(tmp_path: Path, capsys):
    lic_file = tmp_path / "license.json"
    lic_file.write_text(json.dumps({
        "entitlements": {
            "tier": "PRO",
            "max_concurrent_tasks": 4,
            "features": ["feature_a"],
        }
    }), encoding="utf-8")

    ret_allowed = eb.main(["--license", str(lic_file), "--check", "feature_a", "--json"])
    assert ret_allowed == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["allowed"] is True

    ret_denied = eb.main(["--license", str(lic_file), "--check", "non_existent", "--json"])
    assert ret_denied == 1
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["allowed"] is False


def test_cli_limit(tmp_path: Path, capsys):
    lic_file = tmp_path / "license.json"
    lic_file.write_text(json.dumps({
        "entitlements": {
            "tier": "TEAM",
            "max_concurrent_tasks": 5,
            "features": [],
        }
    }), encoding="utf-8")

    ret = eb.main(["--license", str(lic_file), "--limit", "--json"])
    assert ret == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["max_concurrent_tasks"] == 5
