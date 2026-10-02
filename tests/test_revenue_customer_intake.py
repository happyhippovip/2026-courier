import sys
from unittest.mock import patch, MagicMock
import pytest

from scripts.revenue_customer_intake import submit_intake

@patch("scripts.revenue_customer_intake.requests.post")
def test_submit_intake_success(mock_post, capsys):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    submit_intake("testowner", "testrepo", "1234abcd", "CUST-001")
    
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "json" in kwargs
    payload = kwargs["json"]
    assert "goal_id" in payload
    assert payload["goal_id"].startswith("REVENUE-GOAL-")
    assert payload["goal_text"] == "Revenue Safety Audit for testowner/testrepo"
    assert len(payload["tasks"]) == 1
    task = payload["tasks"][0]
    assert task["task_id"].startswith("REV-")
    assert task["type"] == "revenue_safety_audit"
    assert task["target_owner"] == "testowner"
    assert task["target_repo"] == "testrepo"
    assert task["target_sha"] == "1234abcd"
    assert task["customer_reference"] == "CUST-001"
    
    out, _ = capsys.readouterr()
    assert "Success!" in out

@patch("scripts.revenue_customer_intake.requests.post")
def test_submit_intake_failure(mock_post, capsys):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_post.return_value = mock_resp

    submit_intake("testowner", "testrepo", "1234abcd", "CUST-001")
    
    out, _ = capsys.readouterr()
    assert "Failed: 500 Internal Server Error" in out

def test_main_arguments_error(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["revenue_customer_intake.py", "owner"])
    import runpy
    try:
        runpy.run_path("C:/Users/lol/2026-workspace/2026-courier/scripts/revenue_customer_intake.py", run_name="__main__")
    except SystemExit as e:
        assert e.code == 1
    out, _ = capsys.readouterr()
    assert "Usage: python3 revenue_customer_intake.py" in out

@patch("requests.post")
def test_main_arguments_success(mock_post, monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp
    monkeypatch.setattr("sys.argv", ["revenue_customer_intake.py", "ow", "re", "sh", "cu"])
    import runpy
    runpy.run_path("C:/Users/lol/2026-workspace/2026-courier/scripts/revenue_customer_intake.py", run_name="__main__")
    mock_post.assert_called_once()
