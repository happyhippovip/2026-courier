"""intake_dispatcher: fail-closed validation + env overrides (AUTO-104/108/110)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

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


class ScriptedRun:
    """Per-call stdout script for `gh run list`; workflow dispatch always succeeds."""
    def __init__(self, cmds, listings):
        self.cmds = cmds
        self.listings = list(listings)

    def __call__(self, cmd, **kwargs):
        self.cmds.append(cmd)
        if cmd[:2] == ["gh", "workflow"]:
            return Completed()
        text = self.listings.pop(0) if self.listings else ""
        return type("R", (), {"returncode": 0, "stdout": text, "stderr": ""})()


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
    # before-set {111}, then our dispatch surfaces 222 (delta binding).
    monkeypatch.setattr(subprocess, "run", ScriptedRun(cmds, ["111\n", "222\n111\n"]))
    intake_dispatcher.dispatch_intake(intake)
    dispatch = [c for c in cmds if c[:2] == ["gh", "workflow"]][0]
    assert dispatch[:4] == ["gh", "workflow", "run", "custom_lane.yml"]
    assert "price_currency=USD_42" in dispatch
    state = json.loads(state_file.read_text())
    [task] = state["tasks"].values()
    assert task["worker_id"] == "custom-worker"
    assert task["execution_ref"] == "222"


def test_binds_new_run_not_take_latest(tmp_path, monkeypatch, no_sleep):
    # A concurrent foreign dispatch (333) is newest; ours is 222.
    # Take-latest would bind 333; delta binding must bind 222.
    monkeypatch.chdir(tmp_path)
    intake = write_intake(tmp_path / "good.json", good_payload())
    monkeypatch.setattr(intake_dispatcher.shutil, "which", lambda _: "/usr/bin/gh")
    cmds = []
    monkeypatch.setattr(subprocess, "run",
                        ScriptedRun(cmds, ["111\n", "333\n222\n111\n"]))
    intake_dispatcher.dispatch_intake(intake)
    state = json.loads(Path("central_state.json").read_text())
    [task] = state["tasks"].values()
    assert task["execution_ref"] == "222"


def test_no_new_run_falls_back_to_dispatched(tmp_path, monkeypatch, no_sleep):
    monkeypatch.chdir(tmp_path)
    intake = write_intake(tmp_path / "good.json", good_payload())
    monkeypatch.setattr(intake_dispatcher.shutil, "which", lambda _: "/usr/bin/gh")
    monkeypatch.setenv("COURIER_INTAKE_LOOKUP_ATTEMPTS", "2")
    cmds = []
    monkeypatch.setattr(subprocess, "run", ScriptedRun(cmds, ["111\n", "111\n", "111\n"]))
    intake_dispatcher.dispatch_intake(intake)
    state = json.loads(Path("central_state.json").read_text())
    [task] = state["tasks"].values()
    assert task["execution_ref"] == "DISPATCHED"


def test_state_write_preserves_prior_on_crash(tmp_path, monkeypatch, no_sleep):
    import os as _os
    monkeypatch.chdir(tmp_path)
    intake = write_intake(tmp_path / "good.json", good_payload())
    monkeypatch.setattr(intake_dispatcher.shutil, "which", lambda _: "/usr/bin/gh")
    prior = {"tasks": {"old": {"task_id": "old"}}}
    Path("central_state.json").write_text(json.dumps(prior))
    cmds = []
    monkeypatch.setattr(subprocess, "run", ScriptedRun(cmds, ["111\n", "222\n111\n"]))
    real_replace = _os.replace
    monkeypatch.setattr(_os, "replace",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("crash")))
    with pytest.raises(OSError):
        intake_dispatcher.dispatch_intake(intake)
    monkeypatch.setattr(_os, "replace", real_replace)
    assert json.loads(Path("central_state.json").read_text()) == prior
