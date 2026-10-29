"""WK-028: opening the controller journal in queue_feed must not abort feed_once; no DONE without a verified proof."""
import json
import sqlite3
from datetime import timedelta

import pytest

import courier_core.journal as journal_mod
from courier_core.work_queue import WorkQueue
from courier_worker.queue_feed import feed_once
from tests.release_proof_helper import JournalHome
from tests.test_queue_feed_pr_evidence import AGENT, HOLDER, HOST, NOW, _final_done, _home, _item


def _held(tmp_path):
    home, queue = _home(tmp_path, [_item("HELD", ["docs/held.md"], []), _item("NEXTB", ["docs/b.md"], ["HELD"])])
    jh = JournalHome(tmp_path / "ctrl", nested=False)
    queue.journal = jh.journal
    queue.claim("HELD", HOLDER, 600, host=HOST, now=NOW)
    _final_done(home, journal_proof=jh.accept("HELD"))  # a real proof, but the feed home journal is broken
    return home, queue, jh


def _releases(tmp_path):
    return [l for l in (tmp_path / "queue.jsonl").read_text(encoding="utf-8").splitlines() if '"RELEASE"' in l]


def _assert_blocked(report, tmp_path, queue):
    assert report["outcome"] == "blocked" and report["released"] == [] and report["not_proven"] == ["HELD"]
    assert "JOURNAL_UNAVAILABLE" in report["blocked"] and "NEXTB" not in report["claimed"]
    assert _releases(tmp_path) == []
    assert {i["id"]: i["status"] for i in queue.items(now=NOW)} == {"HELD": "CLAIMED", "NEXTB": "READY"}


def test_missing_journal_blocks_without_done(tmp_path):
    home, queue, _ = _held(tmp_path)
    assert not (home / "courier.db").exists()
    _assert_blocked(feed_once(home, AGENT, HOST, now=NOW), tmp_path, queue)


def test_corrupt_journal_blocks_without_exception(tmp_path):
    home, queue, _ = _held(tmp_path)
    (home / "courier.db").write_bytes(b"this is not a sqlite journal\x00" * 64)
    _assert_blocked(feed_once(home, AGENT, HOST, now=NOW), tmp_path, queue)


@pytest.mark.parametrize("exc", [sqlite3.OperationalError("database is locked"),
                                 journal_mod.JournalError("locked"), PermissionError("denied")])
def test_locked_journal_blocks_without_exception(tmp_path, monkeypatch, exc):
    home, queue, _ = _held(tmp_path)
    (home / "courier.db").write_bytes(b"")

    def locked(self):
        raise exc
    monkeypatch.setattr(journal_mod.Journal, "open", locked)  # test-only: simulate the lock, prod path unchanged
    _assert_blocked(feed_once(home, AGENT, HOST, now=NOW), tmp_path, queue)


def test_unexpected_errors_are_not_swallowed(tmp_path, monkeypatch):
    home, _queue, _ = _held(tmp_path)
    (home / "courier.db").write_bytes(b"")

    def bug(self):
        raise ValueError("programming error")
    monkeypatch.setattr(journal_mod.Journal, "open", bug)
    with pytest.raises(ValueError):
        feed_once(home, AGENT, HOST, now=NOW)


def test_real_proof_releases_once_and_restart_gives_no_second_release(tmp_path):
    home, queue = _home(tmp_path, [_item("HELD", ["docs/held.md"], [])])
    jh = JournalHome(home, nested=False)
    queue.journal = jh.journal
    queue.claim("HELD", HOLDER, 600, host=HOST, now=NOW)
    proof = jh.accept("HELD")
    _final_done(home, journal_proof=proof)
    assert feed_once(home, AGENT, HOST, now=NOW)["released"] == ["HELD"]
    jh.restart()  # controller restart on the same courier.db
    again = feed_once(home, AGENT, HOST, now=NOW + timedelta(seconds=5))
    assert again["released"] == [] and again["claimed"] == []
    assert [json.loads(l)["proof"] for l in _releases(tmp_path)] == [proof]
    assert [i["status"] for i in WorkQueue(tmp_path / "items", tmp_path / "queue.jsonl").items(now=NOW)] == ["DONE"]
