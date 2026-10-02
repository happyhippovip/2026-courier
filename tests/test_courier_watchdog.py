import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure we can import courier_watchdog by adding scripts to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

# We must mock os.environ BEFORE importing the module if we want to change API_URL 
# or HEADERS because they are initialized at module load time.
# But since run_loop uses the module's HEADERS directly which uses API_KEY from load time,
# we have to patch both or re-import the module in the tests.
# Actually we can just patch the variables inside the module directly.

from scripts.courier_watchdog import run_loop, log

def test_run_loop_missing_api_key():
    with patch("scripts.courier_watchdog.API_KEY", None):
        with pytest.raises(SystemExit) as exc:
            run_loop()
        assert "COURIER_API_KEY is required" in str(exc.value)

def test_run_loop_success(capsys):
    with patch("scripts.courier_watchdog.API_KEY", "test_key"), \
         patch("scripts.courier_watchdog.HEADERS", {"Authorization": "Bearer test_key", "Content-Type": "application/json"}), \
         patch("scripts.courier_watchdog.requests.post") as mock_post, \
         patch("scripts.courier_watchdog.time.sleep", side_effect=KeyboardInterrupt):
         
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"reclaimed_tasks": 2, "quarantined_tasks": 1}
        mock_post.return_value = mock_resp
        
        try:
            run_loop()
        except KeyboardInterrupt:
            pass
            
        mock_post.assert_called_once_with(
            "http://127.0.0.1:8080/tasks/reclaim_stale",
            headers={"Authorization": "Bearer test_key", "Content-Type": "application/json"},
            timeout=10
        )
        
        out = capsys.readouterr().out
        assert "[Watchdog] Starting Courier Watchdog pointing to http://127.0.0.1:8080" in out
        assert "[Watchdog] Reclaimed 2 tasks from stale workers." in out
        assert "[Watchdog] Quarantined 1 tasks with ambiguous post-crash effects." in out

def test_run_loop_success_no_actions(capsys):
    with patch("scripts.courier_watchdog.API_KEY", "test_key"), \
         patch("scripts.courier_watchdog.requests.post") as mock_post, \
         patch("scripts.courier_watchdog.time.sleep", side_effect=KeyboardInterrupt):
         
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"reclaimed_tasks": 0, "quarantined_tasks": 0}
        mock_post.return_value = mock_resp
        
        try:
            run_loop()
        except KeyboardInterrupt:
            pass
            
        out = capsys.readouterr().out
        assert "Reclaimed" not in out
        assert "Quarantined" not in out

def test_run_loop_status_not_200(capsys):
    with patch("scripts.courier_watchdog.API_KEY", "test_key"), \
         patch("scripts.courier_watchdog.requests.post") as mock_post, \
         patch("scripts.courier_watchdog.time.sleep", side_effect=KeyboardInterrupt):
         
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_post.return_value = mock_resp
        
        try:
            run_loop()
        except KeyboardInterrupt:
            pass
            
        out = capsys.readouterr().out
        # It shouldn't crash, and shouldn't log reclaimed/quarantined
        assert "Reclaimed" not in out
        assert "Quarantined" not in out
        assert "Error calling watchdog endpoint" not in out

def test_run_loop_exception(capsys):
    with patch("scripts.courier_watchdog.API_KEY", "test_key"), \
         patch("scripts.courier_watchdog.requests.post", side_effect=Exception("Network down")), \
         patch("scripts.courier_watchdog.time.sleep", side_effect=KeyboardInterrupt):
         
        try:
            run_loop()
        except KeyboardInterrupt:
            pass
            
        out = capsys.readouterr().out
        assert "[Watchdog] Error calling watchdog endpoint: Network down" in out
