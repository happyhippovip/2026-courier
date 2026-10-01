"""M05-Q2: central_state.json must never be silently wiped or torn.

A corrupt/torn state file must fail closed (SystemExit; intake stays
pending for retry) instead of resetting to {} and overwriting all
recorded tasks. Saves must be atomic (tmp + fsync + replace) so a
crash mid-write cannot tear the file for the next reader.
"""
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
)

from unittest import mock

import pytest

import intake_dispatcher


def _valid_intake(tmp_path):
    intake = tmp_path / "in.json"
    intake.write_text(
        json.dumps(
            {
                "customer_reference": "cust-1",
                "target_owner": "o",
                "target_repo": "r",
                "target_sha": "s",
            }
        )
    )
    return intake


def _mocked_dispatch(monkeypatch, list_runs="[]"):
    ok = mock.Mock()
    ok.returncode = 0
    ok.stdout = ""
    ok.stderr = ""
    lst = mock.Mock()
    lst.returncode = 0
    lst.stdout = list_runs

    def fake_run(cmd, **kwargs):
        if "workflow" in cmd:
            return ok
        return lst

    monkeypatch.setattr(intake_dispatcher.subprocess, "run", fake_run)
    monkeypatch.setattr(intake_dispatcher.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        intake_dispatcher.uuid,
        "uuid4",
        mock.Mock(return_value=mock.Mock(hex="abcd1234")),
    )


def test_corrupt_state_fails_closed_without_wipe(tmp_path, monkeypatch):
    intake = _valid_intake(tmp_path)
    monkeypatch.chdir(tmp_path)
    state_file = tmp_path / "central_state.json"
    state_file.write_bytes(b'{"tasks": {"task-old": {"task_id": "task-old"}}, BROKEN')
    before = state_file.read_bytes()
    _mocked_dispatch(monkeypatch)
    with pytest.raises(SystemExit):
        intake_dispatcher.dispatch_intake(str(intake))
    assert state_file.read_bytes() == before  # no silent wipe
    assert intake.exists()  # stays pending for retry


def test_wrong_shape_state_fails_closed(tmp_path, monkeypatch):
    intake = _valid_intake(tmp_path)
    monkeypatch.chdir(tmp_path)
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({"foo": 1}))
    _mocked_dispatch(monkeypatch)
    with pytest.raises(SystemExit):
        intake_dispatcher.dispatch_intake(str(intake))
    assert json.loads(state_file.read_text()) == {"foo": 1}


def test_existing_tasks_preserved_and_no_tmp_left(tmp_path, monkeypatch):
    intake = _valid_intake(tmp_path)
    monkeypatch.chdir(tmp_path)
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({"tasks": {"task-old": {"task_id": "task-old"}}}))
    _mocked_dispatch(monkeypatch)
    intake_dispatcher.dispatch_intake(str(intake))
    state = json.loads(state_file.read_text())
    assert state["tasks"]["task-old"] == {"task_id": "task-old"}
    assert state["tasks"]["task-revenue-abcd1234"]["execution_ref"] == (
        "DISPATCHED_UNBOUND"
    )
    assert list(tmp_path.glob("*.tmp")) == []


def test_missing_state_file_starts_fresh(tmp_path, monkeypatch):
    intake = _valid_intake(tmp_path)
    monkeypatch.chdir(tmp_path)
    _mocked_dispatch(monkeypatch)
    intake_dispatcher.dispatch_intake(str(intake))
    with open(tmp_path / "central_state.json") as f:
        state = json.load(f)
    assert state["tasks"]["task-revenue-abcd1234"]["task_id"] == (
        "task-revenue-abcd1234"
    )
