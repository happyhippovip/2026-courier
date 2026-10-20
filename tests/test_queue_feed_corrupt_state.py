from pathlib import Path
"""Corrupt feed state must surface, never silently reset.

Covers courier_worker/queue_feed.py _read_json + feed_once call sites:
a missing file still yields the default; a corrupt file raises
CorruptStateError and feed_once reports an explicit corrupt outcome.
"""
import json

import pytest

from courier_worker.queue_feed import CorruptStateError, _read_json, _atomic_write, feed_once


def test_missing_file_returns_default(tmp_path):
    assert _read_json(tmp_path / "nope.json", {"a": 1}) == {"a": 1}


def test_corrupt_file_raises_instead_of_reset(tmp_path):
    bad = tmp_path / "state.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(CorruptStateError):
        _read_json(bad, {})


def test_feed_once_without_config_is_off(tmp_path):
    assert feed_once(tmp_path, "agent-1", "host-1") == {"outcome": "off"}


def test_feed_once_with_corrupt_config_reports_corrupt(tmp_path):
    (tmp_path / "work_queue_feed.json").write_text("{corrupt", encoding="utf-8")
    report = feed_once(tmp_path, "agent-1", "host-1")
    assert report["outcome"] == "config-corrupt"
    assert "error" in report


def test_feed_once_with_corrupt_bridge_state_reports_corrupt(tmp_path):
    items = tmp_path / "items"
    items.mkdir()
    (tmp_path / "ledger.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "work_queue_feed.json").write_text(json.dumps({
        "holder": "holder-1",
        "items_dir": str(items),
        "ledger": str(tmp_path / "ledger.jsonl"),
    }), encoding="utf-8")
    (tmp_path / "ledger_bridge_state.json").write_text("{corrupt", encoding="utf-8")
    report = feed_once(tmp_path, "agent-1", "host-1")
    assert report["outcome"] == "bridge-state-corrupt"


def test_read_json_symlink_refused(tmp_path, monkeypatch):
    symlink_file = tmp_path / "link.json"
    symlink_file.write_text('{"key": "val"}', encoding="utf-8")
    monkeypatch.setattr(Path, "is_symlink", lambda self: True if self == symlink_file else False)
    with pytest.raises(CorruptStateError, match="refusing insecure state read"):
        _read_json(symlink_file, {})


def test_atomic_write_symlink_refused(tmp_path, monkeypatch):
    target = tmp_path / "link_target.json"
    monkeypatch.setattr(Path, "is_symlink", lambda self: True if self == target else False)
    with pytest.raises(CorruptStateError, match="refusing insecure state write"):
        _atomic_write(target, {"data": 123})


def test_atomic_write_fsync_and_retry_resilience(tmp_path, monkeypatch):
    import os
    target = tmp_path / "output.json"
    data = {"status": "ACTIVE", "items": [1, 2, 3]}

    attempts = {"count": 0}
    real_replace = os.replace

    def flaky_replace(src, dst):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise PermissionError("Simulated transient Windows file lock")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)
    _atomic_write(target, data)
    assert attempts["count"] == 3
    assert json.loads(target.read_text(encoding="utf-8")) == data
