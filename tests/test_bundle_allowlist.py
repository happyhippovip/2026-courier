import pytest
import os
from pathlib import Path
import tempfile
import sys

# Add scripts to path so we can import
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.check_bundle_allowlist import check_bundle

def test_bundle_allowlist_missing_required():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        # Empty bundle should complain about missing requirements
        errors = check_bundle(tdp)
        assert any("Missing required runtime path: courier_core" in e for e in errors)
        assert any("Missing required runtime path: courier_worker" in e for e in errors)

def test_bundle_allowlist_internal_leak():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        # Make required paths
        for req in ["courier_core/schemas", "courier_worker", "courier_hub"]:
            (tdp / req).mkdir(parents=True)
            
        # Create an internal leak
        leak_dir = tdp / "config"
        leak_dir.mkdir()
        (leak_dir / "product_strategy.json").touch()
        
        errors = check_bundle(tdp)
        assert any("Confidential internal file leaked" in e and "product_strategy.json" in e for e in errors)

def test_bundle_allowlist_success():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        for req in ["courier_core/schemas", "courier_worker", "courier_hub"]:
            (tdp / req).mkdir(parents=True)
            
        (tdp / "courier_core" / "safe_file.py").touch()
        
        errors = check_bundle(tdp)
        assert not errors, f"Expected no errors, got: {errors}"
