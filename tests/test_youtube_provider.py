import pytest
import os
import shutil
from providers.youtube_provider import YouTubeProvider, MissingCredentialError

@pytest.fixture
def clean_receipts():
    if os.path.exists(".youtube_receipts"):
        shutil.rmtree(".youtube_receipts")
    yield
    if os.path.exists(".youtube_receipts"):
        shutil.rmtree(".youtube_receipts")

@pytest.fixture
def fake_credentials(monkeypatch):
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_SECRET_PATH", "/fake/path")

def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("YOUTUBE_OAUTH_CLIENT_SECRET_PATH", raising=False)
    with pytest.raises(MissingCredentialError):
        YouTubeProvider()

def test_validation_success(fake_credentials):
    provider = YouTubeProvider(dry_run=True)
    payload = {
        "title": "Valid Title",
        "description": "Valid description",
        "tags": ["test", "video"],
        "privacy_status": "private",
        "video_path": "/fake/video.mp4"
    }
    assert provider.validate_payload(payload) is True

def test_validation_title_too_long(fake_credentials):
    provider = YouTubeProvider(dry_run=True)
    payload = {
        "title": "A" * 101,
        "video_path": "/fake/video.mp4"
    }
    with pytest.raises(ValueError, match="Title exceeds 100 characters"):
        provider.validate_payload(payload)

def test_validation_missing_video_path(fake_credentials):
    provider = YouTubeProvider(dry_run=True)
    payload = {
        "title": "A Valid Title"
    }
    with pytest.raises(ValueError, match="video_path is required"):
        provider.validate_payload(payload)

def test_dry_run_upload(fake_credentials, clean_receipts):
    provider = YouTubeProvider(dry_run=True)
    payload = {
        "title": "Test Video",
        "video_path": "/fake/video.mp4"
    }
    receipt = provider.upload_video(payload, idempotency_key="test-key-123")
    assert receipt["status"] == "dry_run"
    assert receipt["video_id"] == "dry_run_video_id"
    
def test_duplicate_suppression(fake_credentials, clean_receipts):
    provider = YouTubeProvider(dry_run=True)
    payload = {
        "title": "Test Video",
        "video_path": "/fake/video.mp4"
    }
    # First upload (dry run) creates receipt
    receipt1 = provider.upload_video(payload, idempotency_key="dup-key")
    # Change payload (simulate user changing mind but keeping idempotency key)
    payload["title"] = "Changed Title"
    receipt2 = provider.upload_video(payload, idempotency_key="dup-key")
    
    assert receipt1 == receipt2 # Second call should return the first receipt

def test_real_upload_fails_offline(fake_credentials):
    provider = YouTubeProvider(dry_run=False)
    payload = {
        "title": "Test Video",
        "video_path": "/fake/video.mp4"
    }
    with pytest.raises(NotImplementedError, match="Real upload is disabled"):
        provider.upload_video(payload)
