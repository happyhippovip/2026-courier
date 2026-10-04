import pytest
import hashlib
from scripts.courier_verifier_head_prev import verify_artifacts, verify_artifact, log

def test_verify_artifact_missing(tmp_path, capsys):
    assert verify_artifact(str(tmp_path / "missing.txt"), "hash") == False
    assert "Artifact missing" in capsys.readouterr().out

def test_verify_artifact_success(tmp_path):
    f = tmp_path / "art.txt"
    f.write_text("hello")
    expected_hash = hashlib.sha256(b"hello").hexdigest()
    assert verify_artifact(str(f), expected_hash) == True

def test_verify_artifacts_no_artifacts():
    assert verify_artifacts({}, {}) == "FAIL"

def test_verify_artifacts_invalid_target():
    assert verify_artifacts({"target_agent": "unknown"}, {"artifacts": [{"path": "a"}]}) == "FAIL"

def test_verify_artifacts_github_omission_bypass():
    task = {
        "target_agent": "github",
        "artifacts": [{"path": "missing_artifact.txt", "expected_sha256": "abc"}]
    }
    result = {
        "artifacts": [{"path": "other.txt"}]
    }
    assert verify_artifacts(task, result) == "FAIL"
