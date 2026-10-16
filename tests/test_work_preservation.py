"""Tests for Work Preservation Without Mutation (FRZ-05 / FRZ-04)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from scripts.work_preservation import (
    calculate_sha256,
    is_path_safe_to_preserve,
    preserve_uncommitted_work,
)


def test_is_path_safe_to_preserve():
    """Verify security filter blocks sensitive files and allows code files."""
    assert is_path_safe_to_preserve("scripts/worker.py") is True
    assert is_path_safe_to_preserve("tests/test_harness.py") is True
    assert is_path_safe_to_preserve("README.md") is True

    # Blocked sensitive patterns
    assert is_path_safe_to_preserve(".env") is False
    assert is_path_safe_to_preserve("config/.env.local") is False
    assert is_path_safe_to_preserve("id_rsa") is False
    assert is_path_safe_to_preserve("secrets/token.json") is False
    assert is_path_safe_to_preserve("courier.db") is False
    assert is_path_safe_to_preserve("state.sqlite") is False
    assert is_path_safe_to_preserve("data.sock") is False
    assert is_path_safe_to_preserve("__pycache__/mod.cpython-39.pyc") is False


def test_preserve_uncommitted_work_mock_repo(tmp_path: Path):
    """Verify preservation artifacts and manifest generated in isolated test git repo."""
    repo_dir = tmp_path / "repo"
    out_dir = tmp_path / "recovery"
    repo_dir.mkdir()

    # Init git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)

    # Initial commit
    init_file = repo_dir / "init.txt"
    init_file.write_text("initial", encoding="utf-8")
    subprocess.run(["git", "add", "init.txt"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True)

    # Make unstaged change
    init_file.write_text("modified content", encoding="utf-8")

    # Add untracked code file and untracked secret file
    (repo_dir / "new_feature.py").write_text("print('feature')", encoding="utf-8")
    (repo_dir / "secret.env").write_text("API_KEY=12345", encoding="utf-8")

    result = preserve_uncommitted_work(repo_dir=repo_dir, output_dir=out_dir)

    target_path = Path(result["target_dir"])
    assert target_path.is_dir()

    # Verify unstaged diff exists and contains modifications
    unstaged_file = target_path / "unstaged.diff"
    assert unstaged_file.is_file()
    assert "modified content" in unstaged_file.read_text(encoding="utf-8")

    # Verify untracked inventory
    untracked_inv = target_path / "untracked_files.json"
    assert untracked_inv.is_file()
    inv_data = json.loads(untracked_inv.read_text(encoding="utf-8"))
    assert "new_feature.py" in inv_data["preserved"]
    assert "secret.env" in inv_data["filtered_security"]

    # Verify preserved untracked file was copied
    assert (target_path / "untracked" / "new_feature.py").is_file()
    assert not (target_path / "untracked" / "secret.env").exists()

    # Verify bundle exists
    assert (target_path / "repository_head.bundle").is_file()

    # Verify manifest
    manifest_path = Path(result["manifest_path"])
    assert manifest_path.is_file()
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["schema_version"] == "1.0"
    assert len(manifest_data["artifacts"]) >= 3


def test_calculate_sha256(tmp_path: Path):
    """Verify checksum calculation."""
    f = tmp_path / "test.bin"
    f.write_bytes(b"hello world")
    # echo -n "hello world" | sha256sum -> b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
    assert calculate_sha256(f) == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
