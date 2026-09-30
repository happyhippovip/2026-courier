"""queue_processor: atomic claim + logging batch (AUTO-102/107/109)."""
import json
import os
from unittest import mock

import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import queue_processor


def make_pending(tmp_path, name="test_intake.json", payload=None):
    pending = tmp_path / "intakes" / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    task_file = pending / name
    task_file.write_text(json.dumps(payload or {"foo": "bar"}))
    return task_file


def test_process_queue_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    task_file = make_pending(tmp_path)
    with mock.patch("scripts.queue_processor.dispatch_intake") as mock_dispatch:
        queue_processor.process_queue()
    claimed = os.path.join("intakes", "processing", "test_intake.json")
    mock_dispatch.assert_called_once_with(claimed)
    assert not task_file.exists()
    assert (tmp_path / "intakes" / "processed" / "test_intake.json").exists()


def test_process_queue_systemexit_continues_batch(tmp_path, monkeypatch):
    # dispatch_intake signals failure via sys.exit(); the failing intake
    # stays in processing/ for triage but must not abort the rest.
    monkeypatch.chdir(tmp_path)
    make_pending(tmp_path, "fail.json")
    make_pending(tmp_path, "ok.json")
    dispatched = []

    def fake_dispatch(path):
        dispatched.append(path)
        if path.endswith("fail.json"):
            raise SystemExit(1)

    with mock.patch("scripts.queue_processor.dispatch_intake", side_effect=fake_dispatch):
        queue_processor.process_queue()  # must not raise

    assert sorted(os.path.basename(p) for p in dispatched) == ["fail.json", "ok.json"]
    assert (tmp_path / "intakes" / "processed" / "ok.json").exists()
    assert (tmp_path / "intakes" / "processing" / "fail.json").exists()


def test_process_queue_skips_already_claimed(tmp_path, monkeypatch):
    # File vanished between glob and claim (lost the rename race): skip it.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "intakes" / "pending").mkdir(parents=True, exist_ok=True)
    ghost = str(tmp_path / "intakes" / "pending" / "ghost.json")
    with mock.patch("scripts.queue_processor.glob.glob", return_value=[ghost]):
        with mock.patch("scripts.queue_processor.dispatch_intake") as mock_dispatch:
            queue_processor.process_queue()  # must not raise
    mock_dispatch.assert_not_called()


def test_process_queue_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    make_pending(tmp_path, "test_intake_fail.json")
    with mock.patch("scripts.queue_processor.dispatch_intake", side_effect=Exception("Dispatch failed")):
        queue_processor.process_queue()  # must not raise
    # Poisoned file stays in processing/ for triage, never re-queued blindly.
    assert (tmp_path / "intakes" / "processing" / "test_intake_fail.json").exists()
    assert not (tmp_path / "intakes" / "processed" / "test_intake_fail.json").exists()


def test_process_queue_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with mock.patch("scripts.queue_processor.dispatch_intake") as mock_dispatch:
        queue_processor.process_queue()
    mock_dispatch.assert_not_called()
