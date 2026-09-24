import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts import courier_watchdog


def test_resolve_api_key_from_env(monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "env-secret-key")
    assert courier_watchdog.resolve_api_key() == "env-secret-key"


def test_resolve_api_key_from_keyring_lowercase(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)

    def mock_get_password(service, username):
        if service == "courier_worker" and username == "courier_api_key":
            return "keyring-lower-key"
        return None

    with patch("keyring.get_password", side_effect=mock_get_password):
        assert courier_watchdog.resolve_api_key() == "keyring-lower-key"


def test_resolve_api_key_from_keyring_uppercase(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)

    def mock_get_password(service, username):
        if service == "courier_worker" and username == "COURIER_API_KEY":
            return "keyring-upper-key"
        return None

    with patch("keyring.get_password", side_effect=mock_get_password):
        assert courier_watchdog.resolve_api_key() == "keyring-upper-key"


def test_check_and_reclaim_missing_key(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    with patch("keyring.get_password", return_value=None):
        with pytest.raises(SystemExit):
            courier_watchdog.check_and_reclaim(api_url="http://127.0.0.1:8080", api_key=None)


def test_check_and_reclaim_success_200(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {"reclaimed_tasks": 3, "quarantined_tasks": 1}

    with patch("requests.post", return_value=mock_res) as mock_post:
        result = courier_watchdog.check_and_reclaim(
            api_url="http://127.0.0.1:8080", api_key="test-key"
        )
        mock_post.assert_called_once_with(
            "http://127.0.0.1:8080/tasks/reclaim_stale",
            headers={"Authorization": "Bearer test-key", "Content-Type": "application/json"},
            timeout=10,
        )

    assert result["status_code"] == 200
    assert result["reclaimed_tasks"] == 3
    assert result["quarantined_tasks"] == 1

    captured = capsys.readouterr()
    assert "Reclaimed 3 tasks" in captured.out
    assert "Quarantined 1 tasks" in captured.out


def test_check_and_reclaim_server_error_500(capsys):
    mock_res = MagicMock()
    mock_res.status_code = 500

    with patch("requests.post", return_value=mock_res):
        result = courier_watchdog.check_and_reclaim(
            api_url="http://127.0.0.1:8080", api_key="test-key"
        )

    assert result["status_code"] == 500
    captured = capsys.readouterr()
    assert "Server returned HTTP 500" in captured.out


def test_check_and_reclaim_connection_exception(capsys):
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Refused")):
        result = courier_watchdog.check_and_reclaim(
            api_url="http://127.0.0.1:8080", api_key="test-key"
        )

    assert result["status_code"] is None
    assert "Refused" in result["error"]
    captured = capsys.readouterr()
    assert "Error calling watchdog endpoint" in captured.out
