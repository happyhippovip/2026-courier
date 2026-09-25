import os
import sys
import hashlib

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import resource_policy

def test_file_manifest_tracker_missing(tmp_path):
    missing = tmp_path / "does_not_exist.txt"
    h = resource_policy.FileManifestTracker.get_file_hash(missing)
    assert h == "FILE_NOT_FOUND"

def test_file_manifest_tracker_success(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()
    
    h = resource_policy.FileManifestTracker.get_file_hash(f)
    assert h == expected
    
    # Test unchanged logic
    assert resource_policy.FileManifestTracker.is_file_unchanged(f, expected) is True
    assert resource_policy.FileManifestTracker.is_file_unchanged(f, "wrong") is False

def test_build_manifest(tmp_path):
    f1 = tmp_path / "f1.txt"
    f2 = tmp_path / "f2.txt"
    f1.write_text("file 1")
    f2.write_text("file 2")
    
    h1 = hashlib.sha256(b"file 1").hexdigest()
    h2 = hashlib.sha256(b"file 2").hexdigest()
    
    manifest = resource_policy.FileManifestTracker.build_manifest(["f1.txt", "f2.txt"], repo_dir=tmp_path)
    assert manifest["f1.txt"] == h1
    assert manifest["f2.txt"] == h2

def test_chief_context_package_builder(tmp_path):
    f1 = tmp_path / "test.txt"
    f1.write_text("test")
    
    pkg = resource_policy.ChiefContextPackageBuilder.build_compact_package(
        workflow_id="wf-1",
        task_id="task-1",
        instruction="do something",
        scope_files=["test.txt"],
        context_version=42,
        context_delta={"foo": "bar"},
        repo_dir=tmp_path
    )
    
    assert pkg["workflow_id"] == "wf-1"
    assert pkg["task_id"] == "task-1"
    assert pkg["context_version"] == "v42"
    assert pkg["instruction"] == "do something"
    assert "test.txt" in pkg["file_manifest"]
    assert pkg["context_delta"] == {"foo": "bar"}
    assert pkg["raw_chat_history_included"] is False

def test_review_dedupe_tracker():
    # Same hash -> skip review
    review, reason = resource_policy.ReviewDedupeTracker.should_review("abc", "abc")
    assert review is False
    assert "SKIP" in reason
    
    # Different hash -> review
    review, reason = resource_policy.ReviewDedupeTracker.should_review("abc", "def")
    assert review is True
    assert "REQUIRED" in reason
    
    # No previous hash -> review
    review, reason = resource_policy.ReviewDedupeTracker.should_review(None, "def")
    assert review is True

