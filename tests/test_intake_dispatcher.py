"""intake_dispatcher: fail-closed validation + env overrides (AUTO-104/108/110)."""
import json
import os
import subprocess
import sys
import time

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import intake_dispatcher


def write_intake(path, payload):
    path.write_text(json.dumps(payload))
    return str(path)


def good_payload(**over):
    payload = {"target_owner": "o", "target_repo": "r", "target_sha": "s" * 40,
               "customer_reference": "cust-1"}
    payload.update(over)
    return payload


class Completed:
    returncode = 0
    stdout = "123\n"
    stderr = ""


def mock_run_factory(cmds):
    def fake_run(cmd, **kwargs):
        cmds.append(cmd)
        return Completed()
    return fake_run


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _: None)


def test_rejects_missing_required_fields_with_exit3(tmp_path, monkeypatch, no_sleep):
    monkeypatch.chdir(tmp_path)
    intake = write_intake(tmp_path / "bad.json", {"target_owner": "o"})
    with pytest.raises(SystemExit) as exc:
        intake_dispatcher.dispatch_intake(intake)
    assert exc.value.code == 3


def test_unreadable_intake_exits_3(tmp_path, monkeypatch, no_sleep):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "broken.json").write_text("{not json")
    with pytest.raises(SystemExit) as exc:
        intake_dispatcher.dispatch_intake(str(tmp_path / "broken.json"))
    assert exc.value.code == 3


def test_missing_gh_cli_exits_2(tmp_path, monkeypatch, no_sleep):
    monkeypatch.chdir(tmp_path)
    intake = write_intake(tmp_path / "good.json", good_payload())
    monkeypatch.setattr(intake_dispatcher.shutil, "which", lambda _: None)
    with pytest.raises(SystemExit) as exc:
        intake_dispatcher.dispatch_intake(intake)
    assert exc.value.code == 2


def test_env_overrides_workflow_worker_state_and_currency(tmp_path, monkeypatch, no_sleep):
    monkeypatch.chdir(tmp_path)
    intake = write_intake(tmp_path / "good.json", good_payload())
    state_file = tmp_path / "custom_state.json"
    monkeypatch.setenv("COURIER_INTAKE_WORKFLOW", "custom_lane.yml")
    monkeypatch.setenv("COURIER_INTAKE_WORKER_ID", "custom-worker")
    monkeypatch.setenv("COURIER_STATE_PATH", str(state_file))
    monkeypatch.setenv("COURIER_PRICE_CURRENCY", "USD_42")
    monkeypatch.setattr(intake_dispatcher.shutil, "which", lambda _: "/usr/bin/gh")
    cmds = []
    monkeypatch.setattr(subprocess, "run", mock_run_factory(cmds))
    intake_dispatcher.dispatch_intake(intake)
    dispatch = cmds[0]
    assert dispatch[:4] == ["gh", "workflow", "run", "custom_lane.yml"]
    assert "price_currency=USD_42" in dispatch
    state = json.loads(state_file.read_text())
    [task] = state["tasks"].values()
    assert task["worker_id"] == "custom-worker"
    assert task["execution_ref"] == "123"
