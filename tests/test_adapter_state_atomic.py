"""Adapter state writes must be atomic (Wave 3 D3 / Wave 4 hardening).

A crash between write-start and write-complete must never leave a torn
state file: the next adapter run parses state at startup, and torn JSON
would fail every retry (exit 1) instead of resuming.
"""
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load_adapter():
    spec = importlib.util.spec_from_file_location(
        "github_worker_adapter_state_under_test",
        ROOT / "scripts" / "github_worker_adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_state_write_preserves_prior_on_crash_before_replace(tmp_path, monkeypatch):
    adapter = load_adapter()
    task = tmp_path / "dispatch-d1.json"
    task.write_text("{}")
    prior = {"dispatch_id": "d1", "status": "WAITING_FOR_WORKER"}
    adapter.write_state(task, prior)

    real_replace = os.replace

    def crashing_replace(src, dst):
        raise OSError("simulated crash before replace")

    monkeypatch.setattr(os, "replace", crashing_replace)
    with pytest.raises(OSError):
        adapter.write_state(task, {"dispatch_id": "d1", "status": "POSTED"})
    monkeypatch.setattr(os, "replace", real_replace)

    # Prior state must be intact and parseable: resume can continue.
    stored = json.loads(adapter.state_path(task).read_text(encoding="utf-8"))
    assert isinstance(stored.pop("pid"), int)
    assert stored == prior


def test_state_write_leaves_complete_json_and_no_tmp(tmp_path):
    adapter = load_adapter()
    task = tmp_path / "dispatch-d2.json"
    task.write_text("{}")
    state = {"dispatch_id": "d2", "run_id": "123", "status": "POSTED"}
    adapter.write_state(task, state)
    stored = json.loads(adapter.state_path(task).read_text(encoding="utf-8"))
    assert isinstance(stored.pop("pid"), int)
    assert stored == state
    assert list(tmp_path.glob("*.tmp")) == []
