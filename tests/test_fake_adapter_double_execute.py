"""Duplicate Execution guard: FakeAdapter refuses a second execute() on an owned ref.

Spawning a second worker process for the same execution_ref would run the
task twice. The adapter must fail closed while the first execution is owned.
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.resolve()

from app.cannon import adapters, storage


def _task(ref="exec-dup-1"):
    return {"task_id": "t-dup", "execution_ref": ref,
            "fake_mode": "SUCCESS", "fake_delay": 0.01,
            "attempt_id": "a1", "dispatch_id": "d1", "worker_id": "w1"}


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    adapter = adapters.FakeAdapter(
        str(REPO / "scripts/integration_contract.py"), tmp_path / "ws")
    try:
        yield adapter
    finally:
        adapter.close()


def test_double_execute_same_ref_rejected(adapter, tmp_path):
    folder = tmp_path / "ws" / "exec-dup-1"
    adapter.execute(_task(), folder, lambda identity: None)
    with pytest.raises(RuntimeError, match="already owned"):
        adapter.execute(_task(), folder, lambda identity: None)


def test_execute_after_close_allows_retry(adapter, tmp_path):
    folder = tmp_path / "ws" / "exec-retry-1"
    task = _task(ref="exec-retry-1")
    adapter.execute(task, folder, lambda identity: None)
    adapter.close_execution("exec-retry-1")
    adapter.execute(task, folder, lambda identity: None)
