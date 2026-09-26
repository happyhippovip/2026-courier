#!/usr/bin/env python3
"""Targeted unit tests for intake_dispatcher fail-closed loading and atomic state update."""

import json
from pathlib import Path
from unittest import mock
import pytest

from scripts.intake_dispatcher import _load_state, dispatch_intake


def test_load_state_nonexistent(tmp_path):
    state, err = _load_state(tmp_path / "missing.json")
    assert err is None
    assert state == {"tasks": {}}


def test_load_state_valid(tmp_path):
    f = tmp_path / "valid.json"
    f.write_text(json.dumps({"tasks": {"t1": {"status": "DISPATCHED"}}}), encoding="utf-8")
    state, err = _load_state(f)
    assert err is None
    assert "t1" in state["tasks"]


def test_load_state_corrupted_fails_closed(tmp_path):
    f = tmp_path / "corrupted.json"
    f.write_text("{invalid json", encoding="utf-8")
    state, err = _load_state(f)
    assert state is None
    assert "cannot read" in err


def test_dispatch_intake_duplicate_skip(tmp_path):
    state_file = tmp_path / "state.json"
    intake_file = tmp_path / "intake.json"
    intake_file.write_text(json.dumps({
        "customer_reference": "ref-123",
        "target_owner": "owner",
        "target_repo": "repo",
        "target_sha": "sha"
    }), encoding="utf-8")

    # First dispatch
    with mock.patch("scripts.intake_dispatcher.subprocess.run") as mock_run:
        dispatch_intake(str(intake_file), state_path=state_file)
        assert mock_run.call_count == 1

    # Second dispatch with same intake must be skipped
    with mock.patch("scripts.intake_dispatcher.subprocess.run") as mock_run:
        dispatch_intake(str(intake_file), state_path=state_file)
        assert mock_run.call_count == 0


def test_dispatch_intake_corrupted_state_exits(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("not json", encoding="utf-8")
    intake_file = tmp_path / "intake.json"
    intake_file.write_text(json.dumps({"customer_reference": "ref-456"}), encoding="utf-8")

    with pytest.raises(SystemExit):
        dispatch_intake(str(intake_file), state_path=state_file)
