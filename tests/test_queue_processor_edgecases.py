"""C-QUEUE: edge cases for queue_processor.already_recorded / process_queue.

Covers the fail-closed contract in scripts/queue_processor.py that the
existing queue tests only exercise implicitly:
- explicit ADMITTED -> True; DISPATCHING -> False (no skip);
- missing state file -> False;
- corrupt state / malformed intake / intake with missing keys raise, and
  process_queue must fall through (dispatch) or stay pending without
  aborting the rest of the batch.
"""
import json
import os
import sys
import time

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
)

from unittest import mock

from scripts import queue_processor
import intake_dispatcher


from test_queue_redispatch_skip import _intake_dict  # shared helper, single definition


def _task_id(intake):
    return intake_dispatcher.fingerprint_task_id(intake)


def _write_pending(tmp_path, name, content):
    pending = tmp_path / "intakes" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    (tmp_path / "intakes" / "processed").mkdir(parents=True, exist_ok=True)
    target = pending / name
    if isinstance(content, (dict, list)):
        target.write_text(json.dumps(content))
    else:
        target.write_text(content)
    return target


def test_already_recorded_explicit_admitted_is_true(tmp_path, monkeypatch):
    intake_file = _write_pending(tmp_path, "job.json", _intake_dict())
    monkeypatch.chdir(tmp_path)
    task_id = _task_id(_intake_dict())
    (tmp_path / "central_state.json").write_text(
        json.dumps({"tasks": {task_id: {"task_id": task_id, "admission": "ADMITTED"}}})
    )
    assert queue_processor.already_recorded(str(intake_file)) is True


def test_already_recorded_fresh_dispatching_is_false(tmp_path, monkeypatch):
    intake_file = _write_pending(tmp_path, "job.json", _intake_dict())
    monkeypatch.chdir(tmp_path)
    task_id = _task_id(_intake_dict())
    (tmp_path / "central_state.json").write_text(
        json.dumps(
            {
                "tasks": {
                    task_id: {
                        "task_id": task_id,
                        "admission": "DISPATCHING",
                        "dispatched_at": time.time(),
                    }
                }
            }
        )
    )
    assert queue_processor.already_recorded(str(intake_file)) is False


def test_already_recorded_missing_state_is_false(tmp_path, monkeypatch):
    intake_file = _write_pending(tmp_path, "job.json", _intake_dict())
    monkeypatch.chdir(tmp_path)
    assert not (tmp_path / "central_state.json").exists()
    assert queue_processor.already_recorded(str(intake_file)) is False


def test_already_recorded_corrupt_state_raises(tmp_path, monkeypatch):
    intake_file = _write_pending(tmp_path, "job.json", _intake_dict())
    monkeypatch.chdir(tmp_path)
    (tmp_path / "central_state.json").write_text("{corrupt")
    with pytest.raises(ValueError):
        queue_processor.already_recorded(str(intake_file))


def test_already_recorded_malformed_intake_raises(tmp_path, monkeypatch):
    intake_file = _write_pending(tmp_path, "job.json", "{malformed")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        queue_processor.already_recorded(str(intake_file))


def test_already_recorded_intake_missing_keys_raises(tmp_path, monkeypatch):
    intake_file = _write_pending(tmp_path, "job.json", {"customer_reference": "x"})
    monkeypatch.chdir(tmp_path)
    with pytest.raises(KeyError):
        queue_processor.already_recorded(str(intake_file))


def test_process_queue_intake_missing_keys_stays_pending_rest_continues(
    tmp_path, monkeypatch
):
    """Valid JSON without fingerprint keys must not abort the batch."""
    bad = _write_pending(tmp_path, "bad.json", {"customer_reference": "x"})
    good_intake = _intake_dict()
    good = _write_pending(tmp_path, "good.json", good_intake)
    monkeypatch.chdir(tmp_path)

    dispatched = []

    def fake_dispatch(path):
        dispatched.append(os.path.basename(path))
        if os.path.basename(path) == "bad.json":
            raise KeyError("target_owner")
        return None

    with mock.patch.object(
        queue_processor, "dispatch_intake", side_effect=fake_dispatch
    ):
        queue_processor.process_queue()  # must not raise

    assert "good.json" in dispatched
    assert (tmp_path / "intakes" / "processed" / "good.json").exists()
    assert bad.exists()
    assert not good.exists()


@pytest.mark.parametrize("bad_state", ["{corrupt", '{"tasks": []}', '{"no_tasks": {}}'])
def test_process_queue_corrupt_state_falls_through_to_dispatch(
    tmp_path, monkeypatch, bad_state
):
    """Corrupt/unshaped central_state.json fails closed: dispatch still attempted."""
    intake_file = _write_pending(tmp_path, "job.json", _intake_dict())
    monkeypatch.chdir(tmp_path)
    (tmp_path / "central_state.json").write_text(bad_state)
    with mock.patch.object(
        queue_processor, "dispatch_intake", return_value="task-revenue-1"
    ) as mock_dispatch:
        queue_processor.process_queue()  # must not raise
    mock_dispatch.assert_called_once()
    assert not intake_file.exists()
    assert (tmp_path / "intakes" / "processed" / "job.json").exists()
