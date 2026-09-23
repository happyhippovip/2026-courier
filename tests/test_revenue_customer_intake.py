import os
import sys
import pytest
from unittest.mock import patch, MagicMock
import requests

from scripts.revenue_customer_intake import (
    validate_intake_inputs,
    get_server_url,
    get_api_key,
    get_headers,
    submit_intake,
    main,
)


def test_validate_intake_inputs_valid():
    validate_intake_inputs("test-owner", "test_repo.1", "abcdef0123456789", "CUST-REF-001")
    validate_intake_inputs("user123", "cool-project", "1234567", "customer@example.com")


def test_validate_intake_inputs_owner_errors():
    with pytest.raises(ValueError, match="owner must be a non-empty string"):
        validate_intake_inputs("", "repo", "1234567", "cust")
    with pytest.raises(ValueError, match="owner must be a non-empty string"):
        validate_intake_inputs(None, "repo", "1234567", "cust")
    with pytest.raises(ValueError, match="Invalid owner format"):
        validate_intake_inputs("bad/owner", "repo", "1234567", "cust")
    with pytest.raises(ValueError, match="Invalid owner format"):
        validate_intake_inputs("owner;rm -rf", "repo", "1234567", "cust")


def test_validate_intake_inputs_repo_errors():
    with pytest.raises(ValueError, match="repo must be a non-empty string"):
        validate_intake_inputs("owner", "", "1234567", "cust")
    with pytest.raises(ValueError, match="Invalid repo format"):
        validate_intake_inputs("owner", "repo/nested", "1234567", "cust")
    with pytest.raises(ValueError, match="Invalid repo format"):
        validate_intake_inputs("owner", "repo with spaces", "1234567", "cust")


def test_validate_intake_inputs_sha_errors():
    with pytest.raises(ValueError, match="sha must be a non-empty string"):
        validate_intake_inputs("owner", "repo", "", "cust")
    with pytest.raises(ValueError, match="Invalid sha format"):
        validate_intake_inputs("owner", "repo", "short", "cust")  # less than 7 chars
    with pytest.raises(ValueError, match="Invalid sha format"):
        validate_intake_inputs("owner", "repo", "not-a-hex-sha-12345", "cust")
    with pytest.raises(ValueError, match="Invalid sha format"):
        validate_intake_inputs("owner", "repo", "f" * 65, "cust")  # >64 chars


def test_validate_intake_inputs_customer_ref_errors():
    with pytest.raises(ValueError, match="customer_ref must be a non-empty string"):
        validate_intake_inputs("owner", "repo", "1234567", "")
    with pytest.raises(ValueError, match="control characters"):
        validate_intake_inputs("owner", "repo", "1234567", "bad\x00ref")


def test_get_server_url_and_api_key(monkeypatch):
    monkeypatch.setenv("COURIER_SERVER", "http://courier.internal:9000/")
    assert get_server_url() == "http://courier.internal:9000"

    monkeypatch.setenv("COURIER_API_KEY", "env_secret_key_123")
    assert get_api_key() == "env_secret_key_123"

    headers = get_headers()
    assert headers["Authorization"] == "Bearer env_secret_key_123"
    assert headers["Content-Type"] == "application/json"


def test_get_api_key_keyring_fallback(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    mock_keyring = MagicMock()
    mock_keyring.get_password.return_value = "keyring_stored_token"
    with patch.dict("sys.modules", {"keyring": mock_keyring}):
        assert get_api_key() == "keyring_stored_token"


def test_submit_intake_success_200():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"goal_id": "goal-server-assigned-99", "status": "ACTIVE"}

    with patch("requests.post", return_value=mock_response) as mock_post:
        res = submit_intake(
            "org", "repo", "abcdef123456", "cust_ref",
            server_url="http://127.0.0.1:8080",
            api_key="mock_key"
        )
        assert res["success"] is True
        assert res["goal_id"] == "goal-server-assigned-99"
        assert res["status_code"] == 200
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://127.0.0.1:8080/goals"
        assert kwargs["headers"]["Authorization"] == "Bearer mock_key"
        assert kwargs["json"]["workflow_plan"][0]["target_owner"] == "org"


def test_submit_intake_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("requests.post", return_value=mock_response):
        res = submit_intake(
            "org", "repo", "abcdef123456", "cust_ref",
            server_url="http://127.0.0.1:8080",
            api_key="bad_key"
        )
        assert res["success"] is False
        assert res["status_code"] == 401
        assert "HTTP 401" in res["error"]


def test_submit_intake_network_exception():
    with patch("requests.post", side_effect=requests.ConnectionError("Connection refused")):
        res = submit_intake(
            "org", "repo", "abcdef123456", "cust_ref",
            server_url="http://127.0.0.1:8080",
            api_key="mock_key"
        )
        assert res["success"] is False
        assert res["status_code"] is None
        assert "Network error" in res["error"]


def test_main_cli_arg_error(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["revenue_customer_intake.py"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_main_cli_missing_api_key(monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    with patch("scripts.revenue_customer_intake.get_api_key", return_value=None):
        monkeypatch.setattr(sys, "argv", ["revenue_customer_intake.py", "org", "repo", "1234567", "ref"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1


def test_main_cli_validation_failure(monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "test_key")
    monkeypatch.setattr(sys, "argv", ["revenue_customer_intake.py", "invalid/owner", "repo", "1234567", "ref"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_main_cli_success(monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "test_key")
    monkeypatch.setattr(sys, "argv", ["revenue_customer_intake.py", "org", "repo", "abcdef12", "ref"])
    with patch("scripts.revenue_customer_intake.submit_intake", return_value={"success": True, "goal_id": "g-1"}):
        main()
