"""Unit tests for TikTok API Health Check (scripts/tiktok_auth_check.py)."""
import json
import subprocess
import sys
import pytest
from scripts.tiktok_auth_check import check_tiktok_auth, READONLY_SCOPE


def test_tiktok_auth_check_dry_run():
    res = check_tiktok_auth(dry_run=True)
    assert res["status"] == "DRY_RUN_OK"
    assert res["read_only"] is True
    assert res["publish_allowed"] is False
    assert res["scope"] == READONLY_SCOPE
    assert "display_name" in res


def test_tiktok_auth_check_missing_creds(monkeypatch, tmp_path):
    monkeypatch.delenv("TIKTOK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TIKTOK_TOKEN_PATH", raising=False)
    res = check_tiktok_auth(
        dry_run=False,
        token_path=str(tmp_path / "nonexistent_tiktok_token.json")
    )
    assert res["status"] == "MISSING_CREDENTIALS"
    assert res["authenticated"] is False
    assert res["publish_allowed"] is False
    assert res["scope"] == READONLY_SCOPE


def test_tiktok_auth_check_cli_dry_run():
    cmd = [sys.executable, "scripts/tiktok_auth_check.py", "--dry-run", "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["status"] == "DRY_RUN_OK"
    assert data["read_only"] is True
    assert data["publish_allowed"] is False


def test_tiktok_auth_check_repo_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("TIKTOK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TIKTOK_TOKEN_PATH", raising=False)
    secrets_dir = tmp_path / ".secrets"
    secrets_dir.mkdir()
    token_file = secrets_dir / "tiktok_token.json"
    token_file.write_text(json.dumps({"access_token": "mock_token_abc"}), encoding="utf-8")

    # When repo_dir is supplied, resolves token from repo_dir/.secrets/tiktok_token.json
    res = check_tiktok_auth(dry_run=False, repo_dir=str(tmp_path))
    # It will attempt HTTP call with mock_token_abc and fail with AUTH_ERROR (not MISSING_CREDENTIALS)
    assert res["status"] in ("AUTH_ERROR", "AUTHENTICATED")
    assert res["status"] != "MISSING_CREDENTIALS"
