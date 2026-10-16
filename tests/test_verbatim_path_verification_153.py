"""Deterministic and isolated tests for Windows Verbatim Path Verification (SEED 153).

Verifies authentic, fail-closed handling, stripping, canonicalization, and confinement
of Windows verbatim (\\\\?\\, \\\\?\\UNC\\, \\??\\) paths.
"""
import os
from pathlib import Path
import subprocess
import sys
import pytest

from courier_runtime.workspace import (
    is_verbatim_path,
    strip_verbatim,
    to_verbatim_path,
    verify_verbatim_path,
    normalize_path,
    resolve_workspace_child,
)


def test_positive_verbatim_path_local_drive():
    """Valid Windows verbatim path to an existing repo file verifies successfully."""
    repo_file = Path(__file__).resolve().parent.parent / "pyproject.toml"
    verbatim = f"\\\\?\\{str(repo_file)}"

    valid, result = verify_verbatim_path(verbatim, must_exist=True)
    assert valid is True
    assert result == verbatim


def test_positive_forward_slash_verbatim_prefix():
    """Forward-slash variant (//?/) is recognized, stripped, and canonicalized."""
    repo_file = Path(__file__).resolve().parent.parent / "pyproject.toml"
    forward_verbatim = f"//?/{str(repo_file).replace('\\', '/')}"

    assert is_verbatim_path(forward_verbatim) is True
    valid, result = verify_verbatim_path(forward_verbatim, must_exist=True)
    assert valid is True
    assert result.startswith("\\\\?\\")


def test_positive_to_verbatim_conversion():
    """Standard absolute paths and UNC shares convert cleanly to canonical verbatim format."""
    p_drive = Path("C:/data/project/file.txt")
    converted = to_verbatim_path(p_drive)
    assert converted.startswith("\\\\?\\C:\\") or converted.startswith("\\\\?\\c:\\")

    # UNC path conversion
    unc_path = "\\\\fileserver\\shared\\artifact.json"
    converted_unc = to_verbatim_path(unc_path)
    assert converted_unc.startswith("\\\\?\\UNC\\")


def test_positive_verbatim_inside_workdir_confinement(tmp_path):
    """Verbatim path correctly validated when confined inside workdir."""
    workdir = tmp_path / "authorized_workspace"
    workdir.mkdir()
    child_file = workdir / "nested" / "output.log"
    child_file.parent.mkdir()
    child_file.write_text("ok")

    verbatim_child = f"\\\\?\\{str(child_file)}"
    valid, result = verify_verbatim_path(verbatim_child, must_exist=True, inside_workdir=workdir)
    assert valid is True
    assert result == verbatim_child


def test_negative_non_verbatim_path_rejected():
    """Standard non-verbatim paths fail closed with NOT_VERBATIM."""
    valid, reason = verify_verbatim_path("C:\\regular\\path\\file.txt")
    assert valid is False
    assert "NOT_VERBATIM" in reason


def test_negative_verbatim_escaping_workdir(tmp_path):
    """Verbatim path escaping authorized workdir fails closed with VERBATIM_ESCAPES_WORKSPACE."""
    workdir = tmp_path / "jail"
    workdir.mkdir()
    outside = tmp_path / "outside" / "secret.key"
    outside.parent.mkdir()
    outside.write_text("secret")

    verbatim_outside = f"\\\\?\\{str(outside)}"
    valid, reason = verify_verbatim_path(verbatim_outside, inside_workdir=workdir)
    assert valid is False
    assert "VERBATIM_ESCAPES_WORKSPACE" in reason


def test_negative_malformed_verbatim_relative():
    """Verbatim prefix followed by a relative path is rejected as malformed."""
    valid, reason = verify_verbatim_path("\\\\?\\relative_dir\\file.txt")
    assert valid is False
    assert "VERBATIM_MALFORMED" in reason


def test_negative_nonexistent_target_when_must_exist(tmp_path):
    """Non-existent file fails closed when must_exist=True."""
    ghost = tmp_path / "ghost_file_does_not_exist_98765.txt"
    verbatim_ghost = f"\\\\?\\{str(ghost)}"
    valid, reason = verify_verbatim_path(verbatim_ghost, must_exist=True)
    assert valid is False
    assert "VERBATIM_TARGET_NOT_FOUND" in reason


def test_negative_null_byte_rejection():
    """Verbatim path containing null-byte injection fails closed."""
    valid, reason = verify_verbatim_path("\\\\?\\C:\\safe\\dir\0evil.exe")
    assert valid is False
    assert "VERBATIM_PATH_NULL_BYTE" in reason


def test_cli_verify_verbatim_path_subprocess():
    """CLI execution via subprocess validates exit codes and output contracts."""
    py = sys.executable
    script = os.path.join("scripts", "verify_verbatim_path.py")
    repo_file = Path(__file__).resolve().parent.parent / "pyproject.toml"
    valid_verbatim = f"\\\\?\\{str(repo_file)}"

    # 1. Success case
    proc_ok = subprocess.run([py, script, valid_verbatim, "--must-exist"], capture_output=True, text=True)
    assert proc_ok.returncode == 0
    assert "VERBATIM PATH VALID: " in proc_ok.stdout

    # 2. Rejection case
    proc_fail = subprocess.run([py, script, "C:\\not_verbatim.txt"], capture_output=True, text=True)
    assert proc_fail.returncode == 1
    assert "VERBATIM PATH FAILED (REFUSED)" in proc_fail.stdout
