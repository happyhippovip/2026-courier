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


def test_memory_repo_symlink_is_not_read(tmp_path, capsys):
    real = tmp_path / "real"
    real.mkdir()
    (real / "PROJECT_STATE.md").write_text("SECRET-MEMORY-BODY\n", encoding="utf-8")
    link = tmp_path / "linked-memory"
    link.symlink_to(real)
    via = tmp_path / "via"
    via.symlink_to(tmp_path)
    nested = via / "real"
    seen = []
    for label, path in (("file", link), ("parent", nested)):
        try:
            package = build_memory_context_package(path, "")
        except SystemExit as exc:
            seen.append((label, str(exc)))
        else:
            seen.append((label, json.dumps(package)))
    with patch.object(sys, "argv", ["resolve_project_memory.py", "--memory-repo", str(link)]):
        try:
            main()
        except SystemExit as exc:
            seen.append(("main", str(exc)))
        else:
            seen.append(("main", capsys.readouterr().out))
    plain = tmp_path / "plain"
    plain.mkdir()
    secret_file = tmp_path / "secret.md"
    secret_file.write_text("SECRET-FILE-BODY\n", encoding="utf-8")
    (plain / "PROJECT_STATE.md").symlink_to(secret_file)
    (plain / "AGENTS.md").write_text("Agents\n", encoding="utf-8")
    try:
        package = build_memory_context_package(plain, "")
    except SystemExit as exc:
        seen.append(("inner", str(exc)))
    else:
        seen.append(("inner", json.dumps(package)))
    assert "SECRET-MEMORY-BODY" not in json.dumps(seen) and "SECRET-FILE-BODY" not in json.dumps(seen) and seen == [
        ("file", "MEMORY_RESOLVER_ERROR: refusing to follow a symlink"),
        ("parent", "MEMORY_RESOLVER_ERROR: refusing to follow a symlink"),
        ("main", "MEMORY_RESOLVER_ERROR: refusing to follow a symlink"),
        ("inner", "MEMORY_RESOLVER_ERROR: refusing to follow a symlink"),
    ] and secret_file.read_text(encoding="utf-8") == "SECRET-FILE-BODY\n", seen


def test_output_does_not_follow_a_symlink(tmp_path):
    repo = tmp_path / "memory"
    repo.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("keep", encoding="utf-8")
    link = tmp_path / "out.json"
    link.symlink_to(outside)
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked"
    linked.symlink_to(outside_dir)
    errors = []
    for dest in (link, linked / "out.json"):
        test_args = ["resolve_project_memory.py", "--memory-repo", str(repo), "--output", str(dest)]
        with patch.object(sys, "argv", test_args):
            try:
                main()
            except SystemExit as exc:
                errors.append(str(exc))
            else:
                errors.append("wrote")
    leaked = sorted(p.name for p in outside_dir.iterdir())
    assert errors == [
        "MEMORY_RESOLVER_ERROR: refusing to follow a symlink",
        "MEMORY_RESOLVER_ERROR: refusing to follow a symlink",
    ] and outside.read_text(encoding="utf-8") == "keep" and leaked == ["keep.txt"] and link.is_symlink(), (
        errors, outside.read_text(encoding="utf-8")[:80], leaked, link.is_symlink(),
    )
