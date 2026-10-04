import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add scripts directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from memory_router import route_memory

@pytest.fixture
def mock_workspace(tmp_path):
    workspace = tmp_path / "mock_workspace"
    workspace.mkdir()
    
    # Create mock files
    files = [
        "memory/WINDOWS_VERIFICATION_LEDGER.md",
        "WINDOWS_PRODUCTIZATION_REPORT.md",
        "CHIEF_BRAIN_STATE.md",
        "docs/COURIER_4_FORWARD_ONLY_OPERATING_CONTRACT.md",
        "docs/DEFERRED_PRODUCT_PLATFORM_AND_REVENUE_PLAYBOOK_2026-09-10.md"
    ]
    
    for f in files:
        file_path = workspace / f
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("Mock content", encoding="utf-8")
        
    return workspace

def test_route_windows_launcher(mock_workspace):
    result = route_memory("Windows launcher", str(mock_workspace))
    assert "memory/WINDOWS_VERIFICATION_LEDGER.md" in result
    assert "WINDOWS_PRODUCTIZATION_REPORT.md" in result
    assert len(result) == 2

def test_route_freeze_incident(mock_workspace):
    result = route_memory("freeze incident", str(mock_workspace))
    assert "CHIEF_BRAIN_STATE.md" in result
    assert "docs/COURIER_4_FORWARD_ONLY_OPERATING_CONTRACT.md" in result
    assert len(result) == 2

def test_route_marketing(mock_workspace):
    result = route_memory("marketing", str(mock_workspace))
    assert "docs/DEFERRED_PRODUCT_PLATFORM_AND_REVENUE_PLAYBOOK_2026-09-10.md" in result
    assert len(result) == 1

def test_route_personal_information(mock_workspace):
    # Should not route to any public project memory
    result = route_memory("mother personal information", str(mock_workspace))
    assert len(result) == 0

def test_route_generic_project(mock_workspace):
    result = route_memory("courier project setup", str(mock_workspace))
    assert "CHIEF_BRAIN_STATE.md" in result
    assert len(result) == 1
