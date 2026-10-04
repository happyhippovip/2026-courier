import json
import pytest
from pathlib import Path
from unittest.mock import patch
import sys

from scripts.resolve_project_memory import (
    get_memory_commit,
    classify_and_select_files,
    redact_sensitive_content,
    extract_status_labels,
    extract_key_sections,
    build_memory_context_package,
    main,
    fail,
    DEFAULT_MEMORY_REPO_NAME
)

def test_get_memory_commit_no_git(tmp_path):
    assert get_memory_commit(tmp_path) == "0000000000000000000000000000000000000000"

def test_get_memory_commit_with_head(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("1234567890abcdef1234567890abcdef12345678", encoding="utf-8")
    assert get_memory_commit(tmp_path) == "1234567890abcdef1234567890abcdef12345678"

def test_get_memory_commit_with_ref(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("ref: refs/heads/main", encoding="utf-8")
    ref_file = git_dir / "refs" / "heads" / "main"
    ref_file.parent.mkdir(parents=True)
    ref_file.write_text("fedcba0987654321fedcba0987654321fedcba09\n", encoding="utf-8")
    assert get_memory_commit(tmp_path) == "fedcba0987654321fedcba0987654321fedcba09"

def test_get_memory_commit_packed_refs(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("ref: refs/heads/main", encoding="utf-8")
    packed = git_dir / "packed-refs"
    packed.write_text("abcd refs/heads/main\n", encoding="utf-8")
    assert get_memory_commit(tmp_path) == "abcd"

def test_get_memory_commit_ref_not_found(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    head_file = git_dir / "HEAD"
    head_file.write_text("ref: refs/heads/main", encoding="utf-8")
    assert get_memory_commit(tmp_path) == "0000000000000000000000000000000000000000"

def test_classify_and_select_files_requested():
    res = classify_and_select_files("", ["BACKLOG.md", "NONEXISTENT.md"])
    assert "PROJECT_STATE.md" in res
    assert "AGENTS.md" in res
    assert "BACKLOG.md" in res
    assert "NONEXISTENT.md" not in res

def test_classify_and_select_files_instruction():
    res = classify_and_select_files("check the next task")
    assert "BACKLOG.md" in res
    assert "TECHNICAL_CONTEXT.md" not in res

    res2 = classify_and_select_files("what is the architecture")
    assert "TECHNICAL_CONTEXT.md" in res2

def test_redact_sensitive_content():
    text = "Here is my token: 'ghp_123456789012345678901' and password=supersecret"
    res = redact_sensitive_content(text)
    assert "ghp_" not in res
    assert "supersecret" not in res
    assert "[REDACTED_CREDENTIAL]" in res

def test_extract_status_labels():
    text = "This is VERIFIED_CURRENT but also IDEA."
    labels = extract_status_labels(text)
    assert labels == ["VERIFIED_CURRENT", "IDEA"]

def test_extract_key_sections():
    text = "Some intro\n# Section 1\nContent 1\n# Section 2\nContent 2"
    res = extract_key_sections("test.md", text)
    assert res["Overview"] == "Some intro"
    assert res["Section 1"] == "Content 1"
    assert res["Section 2"] == "Content 2"

def test_build_memory_context_package(tmp_path):
    repo = tmp_path / "memory"
    repo.mkdir()
    (repo / "PROJECT_STATE.md").write_text("State: VERIFIED_CURRENT", encoding="utf-8")
    (repo / "AGENTS.md").write_text("Agents", encoding="utf-8")

    pkg = build_memory_context_package(repo, instruction="test")
    assert pkg["memory_repo"] == DEFAULT_MEMORY_REPO_NAME
    assert "PROJECT_STATE.md" in pkg["files_consulted"]
    assert "VERIFIED_CURRENT" in pkg["status_labels"]
    assert "PROJECT_STATE.md" in pkg["relevant_context"]["file_extracts"]

def test_build_memory_context_package_missing_repo(tmp_path):
    with pytest.raises(SystemExit):
        build_memory_context_package(tmp_path / "missing", "")

def test_main(tmp_path, capsys):
    repo = tmp_path / "memory"
    repo.mkdir()
    (repo / "PROJECT_STATE.md").write_text("State: VERIFIED_CURRENT", encoding="utf-8")
    (repo / "AGENTS.md").write_text("Agents", encoding="utf-8")

    test_args = ["resolve_project_memory.py", "--memory-repo", str(repo)]
    with patch.object(sys, 'argv', test_args):
        main()
    
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["memory_repo"] == DEFAULT_MEMORY_REPO_NAME

def test_main_output_file(tmp_path):
    repo = tmp_path / "memory"
    repo.mkdir()
    out = tmp_path / "out.json"
    
    test_args = ["resolve_project_memory.py", "--memory-repo", str(repo), "--output", str(out)]
    with patch.object(sys, 'argv', test_args):
        main()
    
    assert out.exists()
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["memory_repo"] == DEFAULT_MEMORY_REPO_NAME
