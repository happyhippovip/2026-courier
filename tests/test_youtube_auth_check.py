"""Unit tests for YouTube API Health Check (scripts/youtube_auth_check.py)."""
import subprocess
import sys
import json
import pytest
from scripts.youtube_auth_check import check_youtube_auth, READONLY_SCOPE


def test_youtube_auth_check_dry_run():
    res = check_youtube_auth(dry_run=True)
    assert res["status"] == "DRY_RUN_OK"
    assert res["read_only"] is True
    assert res["publish_allowed"] is False
    assert res["scope"] == READONLY_SCOPE
    assert "channel_title" in res


def test_youtube_auth_check_missing_creds(monkeypatch, tmp_path):
    monkeypatch.delenv("YOUTUBE_OAUTH_TOKEN_PATH", raising=False)
    monkeypatch.delenv("YOUTUBE_OAUTH_CLIENT_SECRET_PATH", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    res = check_youtube_auth(
        dry_run=False,
        token_path=str(tmp_path / "nonexistent_token.json"),
        client_secret_path=str(tmp_path / "nonexistent_secret.json")
    )
    assert res["status"] == "MISSING_CREDENTIALS"
    assert res["authenticated"] is False
    assert res["publish_allowed"] is False
    assert res["scope"] == READONLY_SCOPE


def test_youtube_auth_check_cli_dry_run():
    cmd = [sys.executable, "scripts/youtube_auth_check.py", "--dry-run", "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["status"] == "DRY_RUN_OK"
    assert data["read_only"] is True
    assert data["publish_allowed"] is False


def test_youtube_auth_check_repo_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("YOUTUBE_OAUTH_TOKEN_PATH", raising=False)
    monkeypatch.delenv("YOUTUBE_OAUTH_CLIENT_SECRET_PATH", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    secrets_dir = tmp_path / ".secrets"
    secrets_dir.mkdir()
    secret_file = secrets_dir / "client_secret.json"
    secret_file.write_text(json.dumps({"installed": {"client_id": "test"}}), encoding="utf-8")

    res = check_youtube_auth(dry_run=False, repo_dir=str(tmp_path))
    # It detects client_secret.json via repo_dir, and reports TOKEN_PENDING or DEPENDENCIES_MISSING/AUTH_ERROR
    assert res["status"] in ("TOKEN_PENDING", "DEPENDENCIES_MISSING", "AUTH_ERROR")
    assert res["status"] != "MISSING_CREDENTIALS"


def test_youtube_auth_check_main_cli(tmp_path, capsys):
    from scripts.youtube_auth_check import main
    code = main(["--dry-run", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "DRY_RUN_OK"
