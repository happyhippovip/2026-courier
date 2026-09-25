import pytest
import os
import json
import sys
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import entitlement_boundary

def test_load_entitlements_default(tmp_path):
    # Pass a path that doesn't exist
    missing_path = tmp_path / "missing.json"
    ents = entitlement_boundary.load_entitlements(str(missing_path))
    assert ents["tier"] == "COMMUNITY"
    assert ents["max_concurrent_tasks"] == 2
    assert "local_execution" in ents["features"]

def test_load_entitlements_valid(tmp_path):
    lic_path = tmp_path / "license.json"
    lic_path.write_text(json.dumps({
        "entitlements": {
            "tier": "ENTERPRISE",
            "max_concurrent_tasks": 100,
            "features": ["local_execution", "advanced_reporting", "cloud_sync"]
        }
    }))
    
    ents = entitlement_boundary.load_entitlements(str(lic_path))
    assert ents["tier"] == "ENTERPRISE"
    assert ents["max_concurrent_tasks"] == 100
    assert "cloud_sync" in ents["features"]

def test_load_entitlements_invalid_json(tmp_path):
    lic_path = tmp_path / "license.json"
    lic_path.write_text("invalid json {")
    
    ents = entitlement_boundary.load_entitlements(str(lic_path))
    assert ents["tier"] == "COMMUNITY"

def test_check_capability(tmp_path):
    lic_path = tmp_path / "license.json"
    lic_path.write_text(json.dumps({
        "entitlements": {
            "features": ["magic_feature"]
        }
    }))
    
    with mock.patch("scripts.entitlement_boundary.load_entitlements", return_value={"features": ["magic_feature"]}):
        assert entitlement_boundary.check_capability("magic_feature") is True
        assert entitlement_boundary.check_capability("other_feature") is False

def test_get_task_limit():
    with mock.patch("scripts.entitlement_boundary.load_entitlements", return_value={"max_concurrent_tasks": 42}):
        assert entitlement_boundary.get_task_limit() == 42
        
    with mock.patch("scripts.entitlement_boundary.load_entitlements", return_value={}):
        assert entitlement_boundary.get_task_limit() == 1

