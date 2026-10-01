"""M05-Q3: crash between dispatch and queue-move must not re-dispatch.

Fingerprint-stable task ids make recovery idempotent: an intake whose
task is already recorded is moved to processed WITHOUT a second
external dispatch.
"""
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
)

from unittest import mock

from scripts import queue_processor
import intake_dispatcher


def _intake_dict(ref="cust-1"):
    return {
        "customer_reference": ref,
        "target_owner": "o",
        "target_repo": "r",
        "target_sha": "s",
    }


def test_fingerprint_stable_and_unique():
    assert intake_dispatcher.fingerprint_task_id(
        _intake_dict()
    ) == intake_dispatcher.fingerprint_task_id(_intake_dict())
    assert intake_dispatcher.fingerprint_task_id(
        _intake_dict()
    ) != intake_dispatcher.fingerprint_task_id(_intake_dict("cust-2"))


def _layout(tmp_path, intake_dict):
    pending = tmp_path / "intakes" / "pending"
    processed = tmp_path / "intakes" / "processed"
    pending.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    intake_file = pending / "job.json"
    intake_file.write_text(json.dumps(intake_dict))
    return intake_file


def test_recovery_skips_second_external_dispatch(tmp_path, monkeypatch):
    intake_file = _layout(tmp_path, _intake_dict())
    monkeypatch.chdir(tmp_path)
    task_id = intake_dispatcher.fingerprint_task_id(_intake_dict())
    (tmp_path / "central_state.json").write_text(
        json.dumps({"tasks": {task_id: {"task_id": task_id}}})
    )
    with mock.patch.object(
        queue_processor, "dispatch_intake"
    ) as mock_dispatch:
        queue_processor.process_queue()
    mock_dispatch.assert_not_called()
    assert not intake_file.exists()
    assert (tmp_path / "intakes" / "processed" / "job.json").exists()


def test_unrecorded_intake_dispatches_once(tmp_path, monkeypatch):
    intake_file = _layout(tmp_path, _intake_dict())
    monkeypatch.chdir(tmp_path)
    with mock.patch.object(
        queue_processor, "dispatch_intake"
    ) as mock_dispatch:
        queue_processor.process_queue()
    mock_dispatch.assert_called_once()
    assert os.path.basename(mock_dispatch.call_args[0][0]) == "job.json"
    assert (tmp_path / "intakes" / "processed" / "job.json").exists()


def test_repeat_dispatch_overwrites_same_record(tmp_path, monkeypatch):
    intake_file = _layout(tmp_path, _intake_dict())
    monkeypatch.chdir(tmp_path)
    ok = mock.Mock()
    ok.returncode = 0
    ok.stdout = ""
    ok.stderr = ""
    lst = mock.Mock()
    lst.returncode = 0
    lst.stdout = "[]"

    def fake_run(cmd, **kwargs):
        return ok if "workflow" in cmd else lst

    with mock.patch.object(
        intake_dispatcher.subprocess, "run", side_effect=fake_run
    ), mock.patch.object(intake_dispatcher.time, "sleep", lambda s: None):
        intake_dispatcher.dispatch_intake(str(intake_file))
        intake_dispatcher.dispatch_intake(str(intake_file))
    with open(tmp_path / "central_state.json") as f:
        state = json.load(f)
    assert list(state["tasks"]) == [
        intake_dispatcher.fingerprint_task_id(_intake_dict())
    ]
