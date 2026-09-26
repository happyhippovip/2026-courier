"""Guards for intake central-state persistence.

Fail-closed: corrupt central_state.json must raise, never silently reset
to an empty task set (P0 data-loss guard). Save must be atomic valid JSON.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from scripts.intake_dispatcher import _load_central_state, _save_central_state


def test_corrupt_state_raises_and_is_preserved(tmp_path):
    state_file = tmp_path / "central_state.json"
    raw = "{corrupt-json!!!"
    state_file.write_text(raw, encoding="utf-8")
    try:
        _load_central_state(str(state_file))
    except RuntimeError as exc:
        assert "refusing to silently reset" in str(exc)
    else:
        raise AssertionError("expected RuntimeError on corrupt state")
    assert state_file.read_text(encoding="utf-8") == raw


def test_missing_state_returns_empty_tasks(tmp_path):
    state = _load_central_state(str(tmp_path / "central_state.json"))
    assert state == {"tasks": {}}


def test_save_is_atomic_and_preserves_existing_tasks(tmp_path):
    state_file = tmp_path / "central_state.json"
    state = {"tasks": {"task-keep": {"task_id": "task-keep"}}}
    _save_central_state(str(state_file), state)
    loaded = json.loads(state_file.read_text(encoding="utf-8"))
    assert loaded["tasks"]["task-keep"]["task_id"] == "task-keep"
    leftovers = list(tmp_path.glob("central_state.json.*.tmp"))
    assert leftovers == []
