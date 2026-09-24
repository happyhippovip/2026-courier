import json
import pytest
from pathlib import Path

from scripts.resolve_project_memory import (
    MemoryResolverError,
    build_memory_context_package,
    classify_and_select_files,
    extract_key_sections,
    extract_status_labels,
    redact_sensitive_content,
    main,
)


@pytest.fixture
def mock_memory_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "memory_repo"
    repo.mkdir()
    git_dir = repo / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    refs_heads = git_dir / "refs" / "heads"
    refs_heads.mkdir(parents=True)
    commit = "d" * 40
    (refs_heads / "main").write_text(commit + "\n", encoding="utf-8")

    (repo / "PROJECT_STATE.md").write_text(
        "# Project State\n\n## Overview\nVERIFIED_CURRENT: Engine running\n",
        encoding="utf-8"
    )
    (repo / "AGENTS.md").write_text(
        "# Agents\n\n## Roles\nAgent config active\n",
        encoding="utf-8"
    )
    (repo / "TECHNICAL_CONTEXT.md").write_text(
        "# Technical Context\n\n## Stack\nPython 3.14 on Windows\nEXTERNAL_STATUS: TikTok token pending\n",
        encoding="utf-8"
    )
    return repo


def test_classify_and_select_files():
    # Default returns always consulted files
    sel = classify_and_select_files("Run a simple task")
    assert "PROJECT_STATE.md" in sel
    assert "AGENTS.md" in sel

    # Keyword matching
    sel_tech = classify_and_select_files("Check the technical architecture and pipeline")
    assert "TECHNICAL_CONTEXT.md" in sel_tech

    sel_backlog = classify_and_select_files("Find safe next priority in backlog")
    assert "BACKLOG.md" in sel_backlog

    # Explicit files
    sel_explicit = classify_and_select_files("any", requested_files=["DECISIONS.md"])
    assert "DECISIONS.md" in sel_explicit


def test_redact_sensitive_content():
    raw = "Here is my secret token: api_key='sk-abcdef1234567890abcdef' and ghp_12345678901234567890"
    redacted = redact_sensitive_content(raw)
    assert "sk-" not in redacted
    assert "ghp_" not in redacted
    assert "[REDACTED_CREDENTIAL]" in redacted


def test_extract_status_labels():
    text = "The task has status VERIFIED_CURRENT and also CONFLICT with EXTERNAL_STATUS."
    labels = extract_status_labels(text)
    assert labels == ["VERIFIED_CURRENT", "CONFLICT", "EXTERNAL_STATUS"]


def test_extract_key_sections():
    content = "# Main Header\nIntro text\n## Section 1\nContent 1\n## Section 2\nContent 2"
    sections = extract_key_sections("test.md", content)
    assert "Main Header" in sections
    assert "Section 1" in sections
    assert sections["Section 1"] == "Content 1"


def test_build_memory_context_package(mock_memory_repo: Path):
    pkg = build_memory_context_package(
        memory_repo_path=mock_memory_repo,
        instruction="Investigate technical stack",
    )
    assert pkg["memory_commit"] == "d" * 40
    assert "TECHNICAL_CONTEXT.md" in pkg["files_consulted"]
    assert "VERIFIED_CURRENT" in pkg["status_labels"]
    assert "EXTERNAL_STATUS" in pkg["status_labels"]
    assert "TECHNICAL_CONTEXT.md" in pkg["source_references"]


def test_build_memory_context_package_missing_repo_error(tmp_path: Path):
    with pytest.raises(MemoryResolverError, match="Memory repository path does not exist"):
        build_memory_context_package(
            memory_repo_path=tmp_path / "does_not_exist",
        )


def test_main_cli(tmp_path: Path, mock_memory_repo: Path, capsys):
    out_file = tmp_path / "context_package.json"
    code = main([
        "--memory-repo", str(mock_memory_repo),
        "--instruction", "Review technical stack and backlog",
        "--output", str(out_file),
    ])
    assert code == 0
    assert out_file.is_file()

    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["memory_commit"] == "d" * 40
    capsys.readouterr()  # Clear stdout from previous call

    # Test stdout output
    code2 = main([
        "--memory-repo", str(mock_memory_repo),
    ])
    assert code2 == 0
    captured = capsys.readouterr()
    stdout_pkg = json.loads(captured.out)
    assert "files_consulted" in stdout_pkg
