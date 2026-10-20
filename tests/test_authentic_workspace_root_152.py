"""Deterministic and isolated tests for Authentic Workspace Root Discovery (SEED 152).

Verifies authentic, fail-closed discovery of workspace root across Windows paths,
deep nested subdirectories, verbatim prefixes, synthetic workspaces, and forbidden system roots.
"""
import os
from pathlib import Path
import subprocess
import sys
import pytest

from courier_runtime.workspace import (
    find_authentic_workspace_root,
    verify_workspace_root,
    is_forbidden_system_root,
    AuthenticWorkspaceRootError,
    strip_verbatim,
    normalize_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_positive_current_repository_workspace_root():
    """Verify that current repository root is authentically discovered."""
    root = find_authentic_workspace_root(start_path=REPO_ROOT)
    assert root is not None
    assert root.name.lower().startswith("2026-courier")
    assert (root / "pyproject.toml").exists()
    assert (root / ".git").exists() or (root / "courier_runtime").exists()


def test_positive_discovery_from_nested_subdirectory():
    """Verify upward traversal from deeply nested subdirectories."""
    nested = Path(__file__).resolve().parent / "ops"
    nested.mkdir(parents=True, exist_ok=True)
    root = find_authentic_workspace_root(start_path=nested)
    assert root is not None
    assert root.name.lower().startswith("2026-courier")


def test_positive_windows_verbatim_path():
    """Windows verbatim prefix (\\\\?\\) must be cleanly normalized and resolved."""
    current_root = find_authentic_workspace_root(start_path=REPO_ROOT)
    verbatim_path = f"\\\\?\\{str(current_root)}"
    resolved = find_authentic_workspace_root(start_path=verbatim_path)
    assert resolved == current_root


def test_positive_synthetic_workspace_with_markers(tmp_path):
    """Synthetic workspace with custom markers discovered from nested directory."""
    ws = tmp_path / "My Synthetic Workspace"
    sub = ws / "packages" / "deep_module"
    sub.mkdir(parents=True)
    (ws / ".git").mkdir()

    discovered = find_authentic_workspace_root(start_path=sub, required_markers=(".git",))
    assert discovered == ws.resolve()


def test_negative_unmarked_directory_fails_closed(tmp_path):
    """Directories lacking authentic markers fail closed."""
    isolated = tmp_path / "unmarked_dir" / "deep"
    isolated.mkdir(parents=True)

    with pytest.raises(AuthenticWorkspaceRootError) as exc_info:
        find_authentic_workspace_root(start_path=isolated, allow_fallback=False)
    assert "No authentic workspace root found" in str(exc_info.value)

    # With allow_fallback=True, returns None
    assert find_authentic_workspace_root(start_path=isolated, allow_fallback=True) is None


def test_negative_forbidden_system_root():
    """System roots like C:\\ and C:\\Windows must be rejected and never identified as workspace."""
    assert is_forbidden_system_root(Path("C:\\")) is True
    if os.name == "nt":
        sys_root = os.environ.get("SystemRoot", r"C:\Windows")
        assert is_forbidden_system_root(Path(sys_root)) is True

    valid, reason = verify_workspace_root("C:\\Windows")
    assert valid is False
    assert "No authentic workspace root found" in reason or "MISMATCH" in reason


def test_negative_workspace_name_mismatch():
    """Mismatched expected workspace name fails closed."""
    valid, reason = verify_workspace_root(path=REPO_ROOT, expected_name="unauthorized-foreign-repo")
    assert valid is False
    assert "WORKSPACE_NAME_MISMATCH" in reason


def test_cli_verify_workspace_root_subprocess():
    """CLI execution via subprocess validates exit codes and output contracts."""
    py = sys.executable
    script = REPO_ROOT / "scripts" / "verify_workspace_root.py"

    # 1. Success case
    proc_ok = subprocess.run([py, str(script), "--path", str(REPO_ROOT), "--expected-name", REPO_ROOT.name], capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert proc_ok.returncode == 0
    assert "AUTHENTIC WORKSPACE ROOT: " in proc_ok.stdout
    assert REPO_ROOT.name in proc_ok.stdout

    # 2. Rejection case
    proc_fail = subprocess.run([py, str(script), "--path", str(REPO_ROOT), "--expected-name", "fake-repo-999"], capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert proc_fail.returncode == 1
    assert "AUTHENTIC WORKSPACE ROOT FAILED (REFUSED)" in proc_fail.stdout
