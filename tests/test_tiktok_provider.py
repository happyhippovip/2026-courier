import pytest
import os
import shutil
from providers.tiktok_provider import TikTokProvider, MissingCredentialError

@pytest.fixture
def clean_receipts():
    if os.path.exists(".tiktok_receipts"):
        shutil.rmtree(".tiktok_receipts")
    yield
    if os.path.exists(".tiktok_receipts"):
        shutil.rmtree(".tiktok_receipts")

@pytest.fixture
def fake_credentials(monkeypatch):
    monkeypatch.setenv("TIKTOK_ACCESS_TOKEN", "fake_tiktok_access_token_12345")

def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("TIKTOK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TIKTOK_CLIENT_KEY", raising=False)
    with pytest.raises(MissingCredentialError):
        TikTokProvider()

def test_validation_success(fake_credentials):
    provider = TikTokProvider(dry_run=True)
    payload = {
        "title": "3D AI Short: Dancing Orange #fruitki #3d",
        "privacy_level": "PUBLIC_TO_EVERYONE",
        "video_path": "/fake/tiktok_video.mp4"
    }
    assert provider.validate_payload(payload) is True

def test_validation_title_too_long(fake_credentials):
    provider = TikTokProvider(dry_run=True)
    payload = {
        "title": "A" * 2201,
        "video_path": "/fake/tiktok_video.mp4"
    }
    with pytest.raises(ValueError, match="Caption exceeds 2200 characters"):
        provider.validate_payload(payload)

def test_validation_invalid_privacy(fake_credentials):
    provider = TikTokProvider(dry_run=True)
    payload = {
        "title": "Valid Caption",
        "privacy_level": "INVALID_PRIVACY",
        "video_path": "/fake/tiktok_video.mp4"
    }
    with pytest.raises(ValueError, match="Invalid privacy_level"):
        provider.validate_payload(payload)

def test_validation_missing_video_path(fake_credentials):
    provider = TikTokProvider(dry_run=True)
    payload = {
        "title": "Valid Title"
    }
    with pytest.raises(ValueError, match="video_path is required"):
        provider.validate_payload(payload)

def test_dry_run_upload(fake_credentials, clean_receipts):
    provider = TikTokProvider(dry_run=True)
    payload = {
        "title": "Test TikTok Short",
        "video_path": "/fake/tiktok_video.mp4"
    }
    receipt = provider.upload_video(payload, idempotency_key="tt-test-key-123")
    assert receipt["status"] == "dry_run"
    assert receipt["publish_id"] == "dry_run_tiktok_publish_id"

def test_duplicate_suppression(fake_credentials, clean_receipts):
    provider = TikTokProvider(dry_run=True)
    payload = {
        "title": "Original TikTok Short",
        "video_path": "/fake/tiktok_video.mp4"
    }
    receipt1 = provider.upload_video(payload, idempotency_key="tt-dup-key")
    payload["title"] = "Modified Caption"
    receipt2 = provider.upload_video(payload, idempotency_key="tt-dup-key")
    assert receipt1 == receipt2

def test_real_upload_fails_offline(fake_credentials):
    provider = TikTokProvider(dry_run=False)
    payload = {
        "title": "Test TikTok Short",
        "video_path": "/fake/tiktok_video.mp4"
    }
    with pytest.raises(NotImplementedError, match="Real upload is disabled"):
        provider.upload_video(payload)
