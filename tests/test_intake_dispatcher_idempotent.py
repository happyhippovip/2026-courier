"""Targeted test: intake_dispatcher admission identity and run binding.

- Same intake admitted twice must not re-dispatch (idempotent admit,
  deterministic task_id per customer_reference).
- execution_ref must bind the run created by OUR dispatch, not just the
  newest run (concurrent-intake misbinding).
- Unreadable central_state.json must fail closed, never silently reset
  (a reset would orphan admitted tasks and cause duplicate dispatches).
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import intake_dispatcher as dispatcher


INTAKE = {
    "target_owner": "o",
    "target_repo": "r",
    "target_sha": "sha123",
    "customer_reference": "cust-42",
}


class FakeCompleted:
    def __init__(self, stdout=""):
        self.stdout = stdout
        self.stderr = ""


def make_fake_gh(calls, run_list):
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["gh", "workflow", "run"]:
            return FakeCompleted("")
        if cmd[:3] == ["gh", "run", "list"]:
            return FakeCompleted(json.dumps(run_list))
        raise AssertionError(f"unexpected command: {cmd}")
    return fake_run


@pytest.fixture()
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dispatcher.time, "sleep", lambda s: None)
    intake_file = tmp_path / "intake.json"
    intake_file.write_text(json.dumps(INTAKE))
    return intake_file


def test_duplicate_admit_skips_redispatch(workdir, monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    calls = []
    monkeypatch.setattr(
        dispatcher.subprocess, "run",
        make_fake_gh(calls, [
            {"databaseId": 111, "createdAt": "2020-01-01T00:00:00Z"},
            {"databaseId": 222, "createdAt": now},
        ]))

    assert dispatcher.dispatch_intake(str(workdir)) == 0
    first_dispatches = [c for c in calls if c[:3] == ["gh", "workflow", "run"]]
    assert len(first_dispatches) == 1

    # Re-admitting the identical intake must not touch gh again.
    assert dispatcher.dispatch_intake(str(workdir)) == 0
    second_dispatches = [c for c in calls if c[:3] == ["gh", "workflow", "run"]]
    assert len(second_dispatches) == 1


def test_execution_ref_binds_own_run_not_newest(workdir, monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    calls = []
    monkeypatch.setattr(
        dispatcher.subprocess, "run",
        make_fake_gh(calls, [
            # Newest run belongs to a concurrent intake (created before ours).
            {"databaseId": 999, "createdAt": "2020-06-01T00:00:00Z"},
            {"databaseId": 777, "createdAt": now},
        ]))
    assert dispatcher.dispatch_intake(str(workdir)) == 0
    state = json.loads(Path("central_state.json").read_text())
    (task,) = state["tasks"].values()
    assert task["execution_ref"] == "777"


def test_missing_customer_reference_refuses(workdir, monkeypatch):
    calls = []
    monkeypatch.setattr(dispatcher.subprocess, "run", make_fake_gh(calls, []))
    bad = workdir.parent / "bad.json"
    bad.write_text(json.dumps({"target_owner": "o"}))
    assert dispatcher.dispatch_intake(str(bad)) == 2
    assert calls == []


def test_corrupt_state_fails_closed(workdir, monkeypatch):
    Path("central_state.json").write_text("{not json")
    calls = []
    monkeypatch.setattr(dispatcher.subprocess, "run", make_fake_gh(calls, []))
    assert dispatcher.dispatch_intake(str(workdir)) == 1
    assert calls == []
    # Corrupt file left untouched for forensics, not overwritten.
    assert Path("central_state.json").read_text() == "{not json"


def test_task_id_deterministic_per_reference(workdir, monkeypatch):
    calls = []
    monkeypatch.setattr(
        dispatcher.subprocess, "run",
        make_fake_gh(calls, [{"databaseId": 1,
                              "createdAt": datetime.now(timezone.utc).isoformat()}]))
    assert dispatcher.dispatch_intake(str(workdir)) == 0
    state = json.loads(Path("central_state.json").read_text())
    (task_id,) = state["tasks"]
    assert task_id.startswith("task-revenue-")
    assert state["tasks"][task_id]["customer_reference"] == "cust-42"


def test_gh_failure_does_not_persist_task(workdir, monkeypatch):
    def boom(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="denied")
    monkeypatch.setattr(dispatcher.subprocess, "run", boom)
    assert dispatcher.dispatch_intake(str(workdir)) == 1
    assert not Path("central_state.json").exists()
