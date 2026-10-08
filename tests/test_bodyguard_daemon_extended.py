import os
import sys
import json
import pytest
from unittest import mock
from pathlib import Path

from scripts.bodyguard_daemon import (
    get_temporary_role,
    execute_task,
    BODYGUARDS,
)

def test_bodyguards_list_length_and_names():
    assert len(BODYGUARDS) == 8
    assert "agent-bodyguard-alpha" in BODYGUARDS
    assert "agent-bodyguard-hotel" in BODYGUARDS
    for bg in BODYGUARDS:
        assert bg.startswith("agent-bodyguard-")

def test_execute_task_hash_determinism(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "events" / "agent-states").mkdir(parents=True)
    
    task = {
        "task_id": "det_task_123",
        "goal_id": "goal_1",
        "attempt_id": 1,
        "dispatch_id": "disp_99"
    }
    
    class FakeProc:
        returncode = 0
        stdout = "output 123"
        stderr = ""
        
    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())
    monkeypatch.setattr("uuid.uuid4", lambda: type("U", (), {"hex": "static_uuid"})())
    
    res = execute_task(task, "agent-bodyguard-alpha", "QA_WORKER")
    assert res["status"] == "SUCCESS"
    assert res["result_id"].startswith("result-")
    assert res["run_id"] == "run-static_uuid"
    assert res["worker_id"] == "agent-bodyguard-alpha"
    # Temporary file must be unlinked
    assert not (tmp_path / "events" / "agent-states" / "det_task_123.json").exists()

def test_execute_task_cleans_up_file_on_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "events" / "agent-states").mkdir(parents=True)
    
    task = {"task_id": "err_task_456"}
    
    def raise_err(*a, **k):
        raise OSError("subproc failure")
        
    monkeypatch.setattr("subprocess.run", raise_err)
    
    res = execute_task(task, "agent-bodyguard-bravo", "TECHNICAL_WORKER")
    assert res["status"] == "FAILED"
    assert "subproc failure" in res["stderr"]
    # Temporary file must not linger
    assert not (tmp_path / "events" / "agent-states" / "err_task_456.json").exists()
