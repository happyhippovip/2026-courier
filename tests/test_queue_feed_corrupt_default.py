"""Queue-feed must survive corrupt state JSON (fail-closed to default).

Pinned by independent review (Muse, 2026-10-19): _read_json catches only
FileNotFoundError, so a corrupt ledger_bridge_state.json / ledger_tasks.json
crashes the feed instead of falling back to the default. Owner fix: catch
JSONDecodeError (plus quarantine) in courier_worker/queue_feed.py.
"""
from courier_worker import queue_feed


def test_read_json_missing_returns_default(tmp_path):
    assert queue_feed._read_json(tmp_path / "nope.json", {}) == {}


def test_read_json_corrupt_returns_default(tmp_path):
    p = tmp_path / "ledger_bridge_state.json"
    p.write_text("{not-json,,,")
    assert queue_feed._read_json(p, {"missions": {}}) == {"missions": {}}
