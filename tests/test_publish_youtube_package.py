import pytest
import os
import json
import shutil
from pathlib import Path
import sys

# Add scripts directory to path for testing
repo_dir = Path(__file__).parent.parent.resolve()
sys.path.append(str(repo_dir / "scripts"))
from publish_youtube_package import publish_package

@pytest.fixture
def fake_manifest(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_data = {
        "mission_id": "test-mission",
        "workflow_id": "test-wf",
        "stages": {
            "READY_TO_PUBLISH": {
                "status": "COMPLETED",
                "details": {
                    "metadata": {
                        "title": "Test Title",
                        "description": "Test Desc",
                        "tags": ["test"],
                        "privacy_status": "private"
                    }
                }
            }
        },
        "artifacts": [
            {
                "stage": "VIDEO_BUILD",
                "relative_path": "video.mp4"
            }
        ]
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f)
        
    # Create fake video file
    with open(tmp_path / "video.mp4", "w") as f:
        f.write("fake video data")
        
    return manifest_path

def test_publish_package_fail_closed_missing_credentials(fake_manifest, monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("YOUTUBE_OAUTH_CLIENT_SECRET_PATH", raising=False)
    # Should fail closed and return False
    assert publish_package(str(fake_manifest), dry_run=True) is False

def test_publish_package_dry_run_success(fake_manifest, monkeypatch):
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_SECRET_PATH", "/fake/path")
    if os.path.exists(".youtube_receipts"):
        shutil.rmtree(".youtube_receipts")
    
    try:
        assert publish_package(str(fake_manifest), dry_run=True) is True
        
        # Verify idempotency key receipt was created
        receipt_path = ".youtube_receipts/yt_test-mission_test-wf.json"
        assert os.path.exists(receipt_path)
        with open(receipt_path, "r") as f:
            receipt = json.load(f)
            assert receipt["status"] == "dry_run"
    finally:
        if os.path.exists(".youtube_receipts"):
            shutil.rmtree(".youtube_receipts")
