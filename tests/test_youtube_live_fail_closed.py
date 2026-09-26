import os
import shutil
from providers.youtube_provider import YouTubeProvider, MissingCredentialError, SCOPES


def test_live_mode_without_real_token_fails_closed(monkeypatch, tmp_path):
    """Live upload without a real token must fail closed with MissingCredentialError."""
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("YOUTUBE_OAUTH_TOKEN_PATH", raising=False)
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_SECRET_PATH", str(tmp_path / "no-such-secret.json"))
    provider = YouTubeProvider(dry_run=False)
    payload = {"title": "Test Video", "video_path": str(tmp_path / "video.mp4")}
    try:
        provider.upload_video(payload)
    except (MissingCredentialError, ValueError):
        return
    raise AssertionError("live upload without token must fail closed")


def test_live_upload_scope_is_youtube_upload():
    assert SCOPES == ["https://www.googleapis.com/auth/youtube.upload"]


def test_dry_run_still_works_with_configured_reference(monkeypatch):
    monkeypatch.setenv("YOUTUBE_OAUTH_CLIENT_SECRET_PATH", "/fake/path")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    provider = YouTubeProvider(dry_run=True)
    receipt = provider.upload_video(
        {"title": "Test Video", "video_path": "/fake/video.mp4"},
        idempotency_key="regression-dry-run",
    )
    assert receipt["status"] == "dry_run"
    # cleanup receipt created in repo root
    if os.path.exists(".youtube_receipts/regression-dry-run.json"):
        os.remove(".youtube_receipts/regression-dry-run.json")
    if os.path.exists(".youtube_receipts") and not os.listdir(".youtube_receipts"):
        shutil.rmtree(".youtube_receipts", ignore_errors=True)
