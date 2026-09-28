import pytest
import json
from pathlib import Path

def test_resolve_project_memory_basic(tmp_path, monkeypatch):
    import scripts.resolve_project_memory as script
    
    # Setup mock memory repo
    repo = tmp_path / "mem_repo"
    repo.mkdir()
    
    # Create git dir
    git_dir = repo / ".git"
    git_dir.mkdir()
    head = git_dir / "HEAD"
    head.write_text("1234567890123456789012345678901234567890\n")
    
    # Create target file
    tech_ctx = repo / "TECHNICAL_CONTEXT.md"
    tech_ctx.write_text("# Overview\nSystem is alive.\n- VERIFIED_CURRENT")
    
    # Mock ALWAYS_CONSULTED_FILES to keep it small
    monkeypatch.setattr(script, "ALWAYS_CONSULTED_FILES", ["TECHNICAL_CONTEXT.md"])
    
    package = script.build_memory_context_package(
        memory_repo_path=repo,
        instruction="Check the technical stack",
        requested_files=None
    )
    
    assert package["memory_commit"] == "1234567890123456789012345678901234567890"
    assert "TECHNICAL_CONTEXT.md" in package["files_consulted"]
    
    assert "VERIFIED_CURRENT" in package["status_labels"]
    
    extract = package["relevant_context"]["file_extracts"]["TECHNICAL_CONTEXT.md"]
    assert "VERIFIED_CURRENT" in extract["status_labels_found"]
    assert "Overview" in extract["sections"]

def test_resolve_project_memory_redaction(tmp_path, monkeypatch):
    import scripts.resolve_project_memory as script
    
    repo = tmp_path / "mem_repo"
    repo.mkdir()
    
    tech_ctx = repo / "TECHNICAL_CONTEXT.md"
    tech_ctx.write_text("# Secrets\npassword='SuperSecretPassword123'\nToken: ghp_123456789012345678901234567890123456\n")
    
    monkeypatch.setattr(script, "ALWAYS_CONSULTED_FILES", ["TECHNICAL_CONTEXT.md"])
    
    package = script.build_memory_context_package(memory_repo_path=repo, instruction="test")
    
    extract = package["relevant_context"]["file_extracts"]["TECHNICAL_CONTEXT.md"]
    text = extract["sections"]["Secrets"]
    
    assert "SuperSecretPassword123" not in text
    assert "ghp_1234567890" not in text
    assert "[REDACTED_CREDENTIAL]" in text

