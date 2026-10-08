import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from scripts.courier_verifier import (
    verify_artifact,
    verify_artifacts,
    VERIFIER_ID,
)

def test_verifier_id_constant():
    assert VERIFIER_ID == "VERIFIER-01"

def test_verify_artifacts_non_list_type():
    task = {}
    result = {"artifacts": "not_a_list"}
    assert verify_artifacts(task, result) == "FAIL"

def test_verify_artifacts_list_of_non_dicts():
    task = {}
    result = {"artifacts": [123, "file.txt"]}
    assert verify_artifacts(task, result) == "FAIL"

def test_verify_artifacts_target_capability_case_insensitivity():
    # If target_capability has 'MAC' in uppercase, it should still recognize remote target
    task = {"target_capability": "MAC_BUILDER"}
    result = {"artifacts": [{"path": "build.bin", "sha256": "abc"}]}
    assert verify_artifacts(task, result) == "FAIL"

def test_verify_artifacts_windows_capability_not_uploaded():
    task = {"target_capability": "WINDOWS_WORKER"}
    result = {"artifacts": [{"path": "build.exe", "sha256": "abc"}]}
    assert verify_artifacts(task, result) == "FAIL"
