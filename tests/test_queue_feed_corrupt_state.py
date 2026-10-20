"""Corrupt feed state must surface, never silently reset.

Covers courier_worker/queue_feed.py _read_json + feed_once call sites:
a missing file still yields the default; a corrupt file raises
CorruptStateError and feed_once reports an explicit corrupt outcome.
"""
import json

import pytest

from courier_worker.queue_feed import CorruptStateError, _read_json, feed_once


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
