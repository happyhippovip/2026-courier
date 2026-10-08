import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.courier_beacon import (
    fetch_metrics,
    halt_system,
    get_bodyguard_invocations,
    COST_PER_INVOCATION,
    HEADERS,
)

def test_cost_constant_and_headers():
    assert COST_PER_INVOCATION == 0.01
    assert "Content-Type" in HEADERS
    assert HEADERS["Content-Type"] == "application/json"

def test_get_bodyguard_invocations_empty_folder(tmp_path, monkeypatch):
    states_dir = tmp_path / "events" / "agent-states"
    states_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    assert get_bodyguard_invocations() == 0

def test_get_bodyguard_invocations_corrupt_files_resilience(tmp_path, monkeypatch):
    states_dir = tmp_path / "events" / "agent-states"
    states_dir.mkdir(parents=True)
    (states_dir / "bad1.json").write_text("{corrupt: json}", encoding="utf-8")
    (states_dir / "bad2.json").write_text("", encoding="utf-8")
    (states_dir / "valid.json").write_text(json.dumps({"model_calls_incurred": 42}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert get_bodyguard_invocations() == 42
