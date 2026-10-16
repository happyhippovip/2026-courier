"""Test Artifact Path Containment (Antigravity 026).

Verifies that worker artifact resolution and storage strictly contain all writes
within the authorized storage root and prevent overwriting original files or
escaping through parent traversal, drive letters, UNC, symlinks/reparse points,
or ambiguous Windows path normalizations.

Tests cover:
A. Normal valid relative path within authorized root.
B. Parent traversal via '..'.
C. Absolute destination paths outside root.
D. Windows drive paths (e.g. C:, D:).
E. Symbolic link or reparse point escaping the root.
F. Attempt to replace an existing protected file (originals preserved).
G. Ambiguous Windows normalizations (DOS devices, ADS, trailing dots/spaces).
"""
import os
import hashlib
import pytest
from pathlib import Path
from scripts.artifact_store import (
    ArtifactError,
    ArtifactStore,
    is_safe_artifact_name,
    resolve_contained_artifact_path,
)

BINDING = {
    "goal_id": "g-026",
    "task_id": "t-026",
    "attempt_id": "t-026:attempt:1",
    "dispatch_id": "disp-026",
    "worker_id": "WINDOWS-026",
}


def test_case_a_normal_relative_path_within_root(tmp_path):
    """Case A: Normal relative path within authorized root succeeds."""
    root = tmp_path / "artifacts_root"
    root.mkdir()

    # Direct child
    target = resolve_contained_artifact_path(root, "result.json")
    assert target == (root / "result.json").resolve()
    assert target.is_relative_to(root.resolve())

    # Nested subpath
    target_nested = resolve_contained_artifact_path(root, "reports/summary.txt")
    assert target_nested == (root / "reports/summary.txt").resolve()
    assert target_nested.is_relative_to(root.resolve())

    # Full ArtifactStore put
    store = ArtifactStore(root)
    rec = store.put(b"test data", name="sub/output.txt", binding=BINDING)
    assert rec["name"] == "sub/output.txt"
    assert (root / "blobs").exists()
    assert store.read_bytes(rec["artifact_id"]) == b"test data"


@pytest.mark.parametrize("traversal", [
    "../escape.txt",
    "../../outside.txt",
    "sub/../../escape.txt",
    "sub/dir/../../../etc/passwd",
    "..\\win_escape.txt",
    "sub\\..\\..\\escape.txt",
])
def test_case_b_parent_traversal_rejected(tmp_path, traversal):
    """Case B: Parent traversal via '..' is strictly rejected."""
    root = tmp_path / "artifacts_root"
    root.mkdir()

    assert not is_safe_artifact_name(traversal)
    with pytest.raises(ArtifactError, match="unsafe artifact name"):
        resolve_contained_artifact_path(root, traversal)

    store = ArtifactStore(root)
    with pytest.raises(ArtifactError):
        store.put(b"bad", name=traversal, binding=BINDING)


@pytest.mark.parametrize("abs_path", [
    "/etc/shadow",
    "/tmp/outside_payload.bin",
    "/var/log/system.log",
    "\\Windows\\System32\\cmd.exe",
    "\\escape\\root.txt",
])
def test_case_c_absolute_path_rejected(tmp_path, abs_path):
    """Case C: Absolute paths outside root are strictly rejected."""
    root = tmp_path / "artifacts_root"
    root.mkdir()

    assert not is_safe_artifact_name(abs_path)
    with pytest.raises(ArtifactError, match="unsafe artifact name"):
        resolve_contained_artifact_path(root, abs_path)

    store = ArtifactStore(root)
    with pytest.raises(ArtifactError):
        store.put(b"bad", name=abs_path, binding=BINDING)


@pytest.mark.parametrize("drive_path", [
    "C:\\secret.txt",
    "C:secret.txt",
    "D:\\data\\outside.bin",
    "D:outside.bin",
    "E:\\system.iso",
    "Z:\\network\\file.txt",
    "\\\\server\\share\\evil.exe",
    "\\\\?\\C:\\raw_disk.txt",
])
def test_case_d_windows_drive_and_unc_paths_rejected(tmp_path, drive_path):
    """Case D: Windows drive-qualified or UNC paths are strictly rejected."""
    root = tmp_path / "artifacts_root"
    root.mkdir()

    assert not is_safe_artifact_name(drive_path)
    with pytest.raises(ArtifactError, match="unsafe artifact name"):
        resolve_contained_artifact_path(root, drive_path)

    store = ArtifactStore(root)
    with pytest.raises(ArtifactError):
        store.put(b"bad", name=drive_path, binding=BINDING)


def test_case_e_symlink_or_reparse_point_escape_rejected(tmp_path):
    """Case E: Symbolic links or directory junctions pointing outside root are caught and rejected."""
    root = tmp_path / "storage_root"
    outside_dir = tmp_path / "outside_dir"
    root.mkdir()
    outside_dir.mkdir()

    # Secret outside file that must NOT be overwritten
    outside_secret = outside_dir / "secret.key"
    outside_secret.write_bytes(b"ORIGINAL_SECRET_BYTES")

    # Symlink directory inside root pointing to outside_dir
    symlink_dir = root / "symlink_escape"
    try:
        os.symlink(outside_dir, symlink_dir)
    except OSError:
        pytest.skip("Symlink creation not permitted in this environment")

    # Candidate path inside the symlink directory
    with pytest.raises(ArtifactError, match="escapes storage root"):
        resolve_contained_artifact_path(root, "symlink_escape/secret.key")

    # Symlink file inside root directly pointing to outside secret
    symlink_file = root / "link_to_secret"
    try:
        os.symlink(outside_secret, symlink_file)
    except OSError:
        pass
    else:
        with pytest.raises(ArtifactError, match="escapes storage root"):
            resolve_contained_artifact_path(root, "link_to_secret")

    # Verify original file remains completely untouched
    assert outside_secret.read_bytes() == b"ORIGINAL_SECRET_BYTES"


def test_case_f_existing_protected_file_cannot_be_overwritten(tmp_path):
    """Case F: Attempting to replace an existing protected file fails and leaves file untouched."""
    root = tmp_path / "storage_root"
    root.mkdir()

    # Protected original file
    protected_file = root / "original_config.json"
    original_bytes = b'{"version": 1, "protected": true}'
    protected_file.write_bytes(original_bytes)
    original_hash = hashlib.sha256(original_bytes).hexdigest()

    # Protection 1: protected_files set
    with pytest.raises(ArtifactError, match="attempt to overwrite protected file"):
        resolve_contained_artifact_path(
            root,
            "original_config.json",
            protected_files={protected_file},
        )

    # Protection 2: allow_overwrite=False prevents any existing file overwrite
    with pytest.raises(ArtifactError, match="attempt to overwrite existing file"):
        resolve_contained_artifact_path(
            root,
            "original_config.json",
            allow_overwrite=False,
        )

    # Verify original file content and hash remain 100% unchanged
    assert protected_file.read_bytes() == original_bytes
    assert hashlib.sha256(protected_file.read_bytes()).hexdigest() == original_hash


@pytest.mark.parametrize("ambiguous_name", [
    "NUL",
    "NUL.txt",
    "CON",
    "CON.dat",
    "PRN",
    "prn.log",
    "AUX",
    "aux.json",
    "COM1",
    "com1.txt",
    "LPT1",
    "lpt1.csv",
    "file.txt:stream",
    "report.json:$DATA",
    "file.txt.",
    "file.txt..",
    "file.txt ",
    " file.txt",
    "sub/NUL.txt",
    "sub/file.txt:ads",
    "sub/trailing.txt.",
])
def test_case_g_ambiguous_windows_normalization_rejected(tmp_path, ambiguous_name):
    """Case G: Windows DOS device names, ADS streams, and trailing dot/space normalizations are rejected."""
    root = tmp_path / "artifacts_root"
    root.mkdir()

    assert not is_safe_artifact_name(ambiguous_name)
    with pytest.raises(ArtifactError, match="unsafe artifact name"):
        resolve_contained_artifact_path(root, ambiguous_name)

    store = ArtifactStore(root)
    with pytest.raises(ArtifactError):
        store.put(b"data", name=ambiguous_name, binding=BINDING)
