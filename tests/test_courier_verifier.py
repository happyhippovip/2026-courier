import sys
import os
import hashlib
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import courier_verifier

def test_verify_artifact_success(tmp_path):
    artifact_path = tmp_path / "test_artifact.txt"
    content = b"hello verifier"
    artifact_path.write_bytes(content)
    expected_hash = hashlib.sha256(content).hexdigest()
    
    assert courier_verifier.verify_artifact(str(artifact_path), expected_hash) == True

def test_verify_artifact_missing(tmp_path):
    artifact_path = tmp_path / "missing_artifact.txt"
    # Should safely return False
    assert courier_verifier.verify_artifact(str(artifact_path), "fakehash") == False

def test_verify_artifact_hash_mismatch(tmp_path):
    artifact_path = tmp_path / "test_artifact_mismatch.txt"
    content = b"hello verifier"
    artifact_path.write_bytes(content)
    # Provide a wrong hash
    assert courier_verifier.verify_artifact(str(artifact_path), "wronghash123") == False

def test_verify_artifact_relative_path(tmp_path):
    # Test falling back to REPO_ROOT when using a relative path
    rel_path = "test_relative.txt"
    
    with mock.patch("scripts.courier_verifier.REPO_ROOT", str(tmp_path)):
        artifact_path = tmp_path / rel_path
        content = b"repo root fallback"
        artifact_path.write_bytes(content)
        expected_hash = hashlib.sha256(content).hexdigest()
        
        # We pass the relative path, but verify_artifact should resolve it using REPO_ROOT
        assert courier_verifier.verify_artifact(rel_path, expected_hash) == True

