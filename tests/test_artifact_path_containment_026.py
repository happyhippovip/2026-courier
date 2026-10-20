"""Tests for artifact path containment, traversal defenses, and existing file protection.

Covers ANTIGRAVITY 026 cases A through G:
A. Normal relative path within authorized root.
B. Parent traversal via '..'.
C. Absolute target path outside root.
D. Windows drive paths.
E. Symlink or reparse point (junction) escaping root.
F. Attempt to replace/overwrite an existing protected file.
G. Target path with ambiguous Windows normalization (DOS devices, trailing dots/spaces, colons).
"""

import hashlib
import json
import os
import subprocess
import pytest
from pathlib import Path

from scripts.artifact_store import ArtifactError, ArtifactStore, is_safe_artifact_name
from courier_worker.host import collect_artifacts, ContainmentError

BINDING = {
    "goal_id": "g-01",
    "task_id": "t-01",
    "attempt_id": "t-01:attempt:1",
    "dispatch_id": "dispatch-01",
    "worker_id": "WINDOWS-01",
}


def test_case_a_normal_relative_path(tmp_path):
    """Case A: Normal relative path within authorized root succeeds."""
    store = ArtifactStore(tmp_path / "store")
    data = b"valid artifact payload"
    rec = store.put(data, name="sub/output.json", binding=BINDING)
    assert rec["size"] == len(data)
    assert rec["name"] == "sub/output.json"
    assert store.read_bytes(rec["artifact_id"]) == data


@pytest.mark.parametrize("traversal", [
    "../escape.txt",
    "sub/../../escape.txt",
    "..\\escape.txt",
    "sub\\..\\..\\escape.txt",
    "....//escape.txt",
])
def test_case_b_parent_traversal(tmp_path, traversal):
    """Case B: Parent traversal via '..' is refused."""
    assert not is_safe_artifact_name(traversal)
    store = ArtifactStore(tmp_path / "store")
    with pytest.raises(ArtifactError, match="unsafe artifact name"):
        store.put(b"bad", name=traversal, binding=BINDING)


@pytest.mark.parametrize("abs_path", [
    "/etc/shadow",
    "/var/log/syslog",
    "\\Windows\\System32\\calc.exe",
    "/root/secret.key",
])
def test_case_c_absolute_target_path(tmp_path, abs_path):
    """Case C: Absolute target path outside root is refused."""
    assert not is_safe_artifact_name(abs_path)
    store = ArtifactStore(tmp_path / "store")
    with pytest.raises(ArtifactError, match="unsafe artifact name"):
        store.put(b"bad", name=abs_path, binding=BINDING)


@pytest.mark.parametrize("drive_path", [
    "C:\\secret.txt",
    "D:\\backup.bak",
    "C:relative_drive.txt",
    "\\\\?\\C:\\verbatim.txt",
    "\\\\server\\share\\data.txt",
])
def test_case_d_windows_drive_and_unc_paths(tmp_path, drive_path):
    """Case D: Windows drive letters, verbatim syntax, and UNC shares are refused."""
    assert not is_safe_artifact_name(drive_path)
    store = ArtifactStore(tmp_path / "store")
    with pytest.raises(ArtifactError, match="unsafe artifact name"):
        store.put(b"bad", name=drive_path, binding=BINDING)


def test_case_e_symlink_reparse_point_boundary(tmp_path):
    """Case E: Symlink / junction pointing outside root is pruned and never collected."""
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sensitive_original.txt").write_bytes(b"sensitive content")
    (workdir / "regular_artifact.txt").write_bytes(b"legitimate artifact")

    # Create a Windows directory junction pointing from inside workdir to outside
    junc = workdir / "junc_link"
    res = subprocess.run(["cmd", "/c", "mklink", "/J", str(junc), str(outside)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode == 0:
        collected = collect_artifacts(str(workdir))
        paths = [a.path.replace("\\", "/") for a in collected]
        # Legitimate file inside root is collected
        assert "regular_artifact.txt" in paths
        # File outside root referenced via junction is NOT collected
        assert not any("sensitive_original.txt" in p for p in paths)
        assert not any("junc_link" in p for p in paths)
    else:
        pytest.skip("Windows junction creation not supported in this test runner environment")


def test_case_f_existing_file_protection(tmp_path):
    """Case F: Attempt to replace or conflict an existing protected file fails closed."""
    store = ArtifactStore(tmp_path / "store")
    data1 = b"original protected payload"
    rec1 = store.put(data1, name="doc.txt", binding=BINDING)
    
    # Same upload is idempotent
    rec_repeat = store.put(data1, name="doc.txt", binding=BINDING)
    assert rec_repeat == rec1

    # Tampering with stored record raises conflict error without modifying existing file
    record_path = store._record_path(rec1["artifact_id"])
    record_content_before = record_path.read_text(encoding="utf-8")
    record_path.write_text(json.dumps({"tampered": True}), encoding="utf-8")

    with pytest.raises(ArtifactError, match="artifact record conflict"):
        store.put(data1, name="doc.txt", binding=BINDING)

    # Restoring record verifies blob is intact
    record_path.write_text(record_content_before, encoding="utf-8")
    assert store.read_bytes(rec1["artifact_id"]) == data1


@pytest.mark.parametrize("ambiguous_name", [
    "output.txt.",     # trailing dot (Windows strips or aliases)
    "output.txt ",     # trailing space (Windows strips)
    "output:stream",   # alternate data stream
    "CON",             # reserved device
    "PRN.txt",         # reserved device with extension
    "AUX",             # reserved device
    "NUL",             # reserved device
    "COM1",            # reserved comm port
    "sub/LPT2.dat",    # reserved device in subdirectory
])
def test_case_g_ambiguous_windows_normalization(tmp_path, ambiguous_name):
    """Case G: Paths with ambiguous Windows normalization are rejected."""
    assert not is_safe_artifact_name(ambiguous_name)
    store = ArtifactStore(tmp_path / "store")
    with pytest.raises(ArtifactError, match="unsafe artifact name"):
        store.put(b"payload", name=ambiguous_name, binding=BINDING)
