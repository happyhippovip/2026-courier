import pytest
from unittest.mock import patch

from scripts.courier_watchdog import (
    STALE_THRESHOLD_SECONDS,
    HEADERS,
    API_URL,
    log,
)

def test_watchdog_constants():
    assert STALE_THRESHOLD_SECONDS == 300
    assert "Content-Type" in HEADERS
    assert HEADERS["Content-Type"] == "application/json"
    assert "127.0.0.1" in API_URL or "localhost" in API_URL

def test_log_output(capsys):
    log("Health check message")
    out = capsys.readouterr().out
    assert "[Watchdog] Health check message\n" == out
