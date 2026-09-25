import pytest
import os
import json
import shutil
from unittest import mock
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import queue_processor

def test_process_queue_success(tmp_path):
    # Mocking os methods for directory creation and file movement to use tmp_path
    
    pending_dir = tmp_path / "intakes" / "pending"
    processed_dir = tmp_path / "intakes" / "processed"
    pending_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    task_file = pending_dir / "test_intake.json"
    task_file.write_text('{"foo": "bar"}')
    
    def mock_glob(pattern):
        if pattern == "intakes/pending/*.json":
            return [str(task_file)]
        return []

    with mock.patch("scripts.queue_processor.os.makedirs"):
        with mock.patch("scripts.queue_processor.glob.glob", side_effect=mock_glob):
            with mock.patch("scripts.queue_processor.dispatch_intake") as mock_dispatch:
                with mock.patch("scripts.queue_processor.shutil.move") as mock_move:
                    queue_processor.process_queue()
                    
    mock_dispatch.assert_called_once_with(str(task_file))
    mock_move.assert_called_once_with(str(task_file), os.path.join("intakes/processed", "test_intake.json"))

def test_process_queue_systemexit_continues_batch(tmp_path):
    # dispatch_intake signals failure via sys.exit(); the failing intake
    # stays pending but must not abort the rest of the batch.
    def mock_glob(pattern):
        if pattern == "intakes/pending/*.json":
            return ["fail.json", "ok.json"]
        return []

    dispatched = []

    def fake_dispatch(path):
        dispatched.append(path)
        if path == "fail.json":
            raise SystemExit(1)

    with mock.patch("scripts.queue_processor.os.makedirs"):
        with mock.patch("scripts.queue_processor.glob.glob", side_effect=mock_glob):
            with mock.patch("scripts.queue_processor.dispatch_intake", side_effect=fake_dispatch):
                with mock.patch("scripts.queue_processor.shutil.move") as mock_move:
                    queue_processor.process_queue()  # must not raise

    assert dispatched == ["fail.json", "ok.json"]
    mock_move.assert_called_once_with("ok.json", os.path.join("intakes/processed", "ok.json"))

def test_process_queue_empty():
    with mock.patch("scripts.queue_processor.os.makedirs"):
        with mock.patch("scripts.queue_processor.glob.glob", return_value=[]):
            with mock.patch("scripts.queue_processor.dispatch_intake") as mock_dispatch:
                queue_processor.process_queue()
                
    mock_dispatch.assert_not_called()

def test_process_queue_error(tmp_path):
    pending_dir = tmp_path / "intakes" / "pending"
    processed_dir = tmp_path / "intakes" / "processed"
    pending_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    task_file = pending_dir / "test_intake_fail.json"
    task_file.write_text('{"foo": "bar"}')
    
    def mock_glob(pattern):
        if pattern == "intakes/pending/*.json":
            return [str(task_file)]
        return []

    with mock.patch("scripts.queue_processor.os.makedirs"):
        with mock.patch("scripts.queue_processor.glob.glob", side_effect=mock_glob):
            with mock.patch("scripts.queue_processor.dispatch_intake", side_effect=Exception("Dispatch failed")):
                with mock.patch("scripts.queue_processor.shutil.move") as mock_move:
                    queue_processor.process_queue()
                    
    # Should catch the exception and NOT move the file
    mock_move.assert_not_called()

