import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add scripts directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from resolve_project_identity import resolve_project_identity

def test_resolve_courier_symphony(tmp_path):
    # Setup mock workspace
    workspace = tmp_path / "2026-courier"
    workspace.mkdir()
    
    # pyproject.toml
    (workspace / "pyproject.toml").write_text('name = "courier"\n', encoding="utf-8")
    
    # CHIEF_BRAIN_STATE.md
    (workspace / "CHIEF_BRAIN_STATE.md").write_text('Project: COURIER 4\n', encoding="utf-8")
    
    # .git/config
    git_dir = workspace / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text('[remote "origin"]\nurl = git@github.com:courier/courier.git\n', encoding="utf-8")
    
    # Test vague query
    result = resolve_project_identity("my project", str(workspace))
    
    assert result["is_courier"] is True
    assert result["canonical_name"] == "Courier Symphony"
    assert result["confidence"] == 110 # 10 + 40 + 30 + 20 + 10

def test_resolve_ambiguous_non_courier(tmp_path):
    # Setup an empty generic workspace
    workspace = tmp_path / "generic_project"
    workspace.mkdir()
    
    result = resolve_project_identity("my project", str(workspace))
    
    assert result["is_courier"] is False
    assert result["canonical_name"] is None
    assert result["confidence"] == 0

def test_resolve_partial_evidence(tmp_path):
    # Setup workspace with some evidence but not all
    workspace = tmp_path / "windows_project"
    workspace.mkdir()
    
    # Only pyproject.toml
    (workspace / "pyproject.toml").write_text('name = "courier"\n', encoding="utf-8")
    
    result = resolve_project_identity("Windows project", str(workspace))
    
    assert result["is_courier"] is True
    assert result["canonical_name"] == "Courier Symphony"
    assert result["confidence"] == 50 # 40 (pyproject) + 10 (vague query matches)
