#!/usr/bin/env python3
"""Tests for scripts/submit_goal.py."""

import json
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
import scripts.submit_goal as submit_goal


def test_get_api_key_from_env(monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "env_secret_key")
    assert submit_goal.get_api_key() == "env_secret_key"


def test_get_api_key_from_keyring(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    with patch("keyring.get_password", side_effect=lambda s, u: "keyring_token" if s == "courier_worker" and u == "courier_api_key" else None):
        assert submit_goal.get_api_key() == "keyring_token"


def test_submit_goal_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"accepted": True}

    with patch("requests.post", return_value=mock_resp):
        res = submit_goal.submit_goal(goal_text="Test Goal Text", api_key="test-key")
        assert res["status"] == "SUCCESS"
        assert res["status_code"] == 200
        assert res["response"] == {"accepted": True}
        assert res["goal_id"].startswith("GOAL-")


def test_submit_goal_api_failure():
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.headers = {"content-type": "text/plain"}
    mock_resp.text = "Forbidden"

    with patch("requests.post", return_value=mock_resp):
        res = submit_goal.submit_goal(goal_text="Test Goal Text")
        assert res["status"] == "FAILED"
        assert res["status_code"] == 403
        assert res["error"] == "Forbidden"


def test_submit_goal_exception():
    with patch("requests.post", side_effect=ConnectionError("Connection refused")):
        res = submit_goal.submit_goal(goal_text="Test Goal Text")
        assert res["status"] == "ERROR"
        assert "Connection refused" in res["error"]


def test_submit_goal_from_json_file(tmp_path: Path):
    payload = {"goal_id": "CUSTOM-123", "workflow_plan": ["step1", "step2"]}
    file_path = tmp_path / "custom_goal.json"
    file_path.write_text(json.dumps(payload), encoding="utf-8")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"status": "ok"}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = submit_goal.submit_goal(json_file=str(file_path))
        assert res["status"] == "SUCCESS"
        assert res["goal_id"] == "CUSTOM-123"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["goal_id"] == "CUSTOM-123"


def test_main_cli_json_mode(capsys):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"received": True}

    with patch("requests.post", return_value=mock_resp):
        ret = submit_goal.main(["Deploy website", "--json"])
        assert ret == 0
        captured = capsys.readouterr().out
        data = json.loads(captured)
        assert data["status"] == "SUCCESS"
        assert data["goal_id"].startswith("GOAL-")


def test_main_cli_no_args():
    ret = submit_goal.main([])
    assert ret == 1
