"""M05-Q4: intake DISPATCHING marker + adopt (record-before-dispatch).

A crash between `gh workflow run` and the state record must not cause a
blind second external dispatch: the marker written BEFORE `gh` lets
recovery adopt the existing run (fresh marker) or re-dispatch exactly
once (stale marker). ADMITTED tasks return without any subprocess call.
"""
import json
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
)

from unittest import mock

import pytest

import intake_dispatcher
from scripts import queue_processor


def _intake_dict():
    return {
        "customer_reference": "cust-1",
        "target_owner": "o",
        "target_repo": "r",
        "target_sha": "s",
    }


def _task_id():
    return intake_dispatcher.fingerprint_task_id(_intake_dict())


def _mocked_gh(monkeypatch, list_runs, workflow_calls):
    ok = mock.Mock()
    ok.returncode = 0
    ok.stdout = ""
    ok.stderr = ""
    lst = mock.Mock()
    lst.returncode = 0
    lst.stdout = json.dumps(list_runs)

    def fake_run(cmd, **kwargs):
        if "workflow" in cmd:
            workflow_calls.append(cmd)
            return ok
        return lst

    monkeypatch.setattr(intake_dispatcher.subprocess, "run", fake_run)
    monkeypatch.setattr(intake_dispatcher.time, "sleep", lambda s: None)


def _write_intake(tmp_path):
    intake = tmp_path / "in.json"
    intake.write_text(json.dumps(_intake_dict()))
    return intake


def _run_after(epoch, rid):
    return {
        "databaseId": rid,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch + 5)),
    }


def test_first_dispatch_records_admitted(tmp_path, monkeypatch):
    intake = _write_intake(tmp_path)
    monkeypatch.chdir(tmp_path)
    workflow_calls = []
    _mocked_gh(monkeypatch, [], workflow_calls)
    returned = intake_dispatcher.dispatch_intake(str(intake))
    assert returned == _task_id()
    assert len(workflow_calls) == 1
    with open(tmp_path / "central_state.json") as f:
        record = json.load(f)["tasks"][_task_id()]
    assert record["admission"] == "ADMITTED"
    assert isinstance(record["dispatched_at"], (int, float))


def test_fresh_marker_adopts_run_without_redispatch(tmp_path, monkeypatch):
    intake = _write_intake(tmp_path)
    monkeypatch.chdir(tmp_path)
    marker_at = time.time() - 10
    (tmp_path / "central_state.json").write_text(
        json.dumps(
            {
                "tasks": {
                    _task_id(): {
                        "task_id": _task_id(),
                        "admission": "DISPATCHING",
                        "dispatched_at": marker_at,
                    }
                }
            }
        )
    )
    workflow_calls = []
    _mocked_gh(monkeypatch, [_run_after(marker_at, "777")], workflow_calls)
    returned = intake_dispatcher.dispatch_intake(str(intake))
    assert returned == _task_id()
    assert workflow_calls == []
    with open(tmp_path / "central_state.json") as f:
        record = json.load(f)["tasks"][_task_id()]
    assert record["admission"] == "ADMITTED"
    assert record["execution_ref"] == "777"


def test_fresh_marker_without_run_stays_pending(tmp_path, monkeypatch):
    intake = _write_intake(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "central_state.json").write_text(
        json.dumps(
            {
                "tasks": {
                    _task_id(): {
                        "task_id": _task_id(),
                        "admission": "DISPATCHING",
                        "dispatched_at": time.time() - 10,
                    }
                }
            }
        )
    )
    workflow_calls = []
    _mocked_gh(monkeypatch, [], workflow_calls)
    with pytest.raises(SystemExit):
        intake_dispatcher.dispatch_intake(str(intake))
    assert workflow_calls == []
    with open(tmp_path / "central_state.json") as f:
        record = json.load(f)["tasks"][_task_id()]
    assert record["admission"] == "DISPATCHING"


def test_stale_marker_redispatches_exactly_once(tmp_path, monkeypatch):
    intake = _write_intake(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "central_state.json").write_text(
        json.dumps(
            {
                "tasks": {
                    _task_id(): {
                        "task_id": _task_id(),
                        "admission": "DISPATCHING",
                        "dispatched_at": time.time() - 3600,
                    }
                }
            }
        )
    )
    workflow_calls = []
    _mocked_gh(monkeypatch, [], workflow_calls)
    intake_dispatcher.dispatch_intake(str(intake))
    assert len(workflow_calls) == 1
    with open(tmp_path / "central_state.json") as f:
        record = json.load(f)["tasks"][_task_id()]
    assert record["admission"] == "ADMITTED"


def test_admitted_returns_without_subprocess(tmp_path, monkeypatch):
    intake = _write_intake(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "central_state.json").write_text(
        json.dumps(
            {"tasks": {_task_id(): {"task_id": _task_id(), "admission": "ADMITTED"}}}
        )
    )
    with mock.patch.object(
        intake_dispatcher.subprocess, "run", side_effect=AssertionError("no gh call")
    ):
        assert intake_dispatcher.dispatch_intake(str(intake)) == _task_id()


def test_queue_precheck_skips_only_admitted(tmp_path, monkeypatch):
    pending = tmp_path / "intakes" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    intake_file = pending / "job.json"
    intake_file.write_text(json.dumps(_intake_dict()))
    monkeypatch.chdir(tmp_path)
    assert queue_processor.already_recorded(str(intake_file)) is False
    (tmp_path / "central_state.json").write_text(
        json.dumps(
            {
                "tasks": {
                    _task_id(): {
                        "task_id": _task_id(),
                        "admission": "DISPATCHING",
                        "dispatched_at": time.time(),
                    }
                }
            }
        )
    )
    assert queue_processor.already_recorded(str(intake_file)) is False
    (tmp_path / "central_state.json").write_text(
        json.dumps({"tasks": {_task_id(): {"task_id": _task_id()}}})
    )
    assert queue_processor.already_recorded(str(intake_file)) is True
