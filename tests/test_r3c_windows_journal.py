"""R3c follow-up: Windows local queue proof path + WK-026 (journal read error => NOT_PROVEN, no exception)."""
import json
import sqlite3
from datetime import datetime, timezone

from courier_core.journal import JournalError
from courier_core.work_queue import WorkQueue, check_release_proof, journal_release_proof, release_task_id
from scripts.windows_worker.local_queue import run_once
from tests.release_proof_helper import FORGED, JournalHome, View

NOW = datetime(2026, 10, 23, 9, 0, 0, tzinfo=timezone.utc)
HOLDER = "windows:WIN-01"


def _setup(tmp_path, journal_override=None):
    items = tmp_path / "items"
    items.mkdir()
    (items / "A.json").write_text(json.dumps({
        "id": "A", "title": "Item A", "lane": "L6", "branch": "cursor/windows-lock-import-be3a",
        "files_scope": ["scripts/windows_worker/a.py"], "depends_on": [], "acceptance": ["x"],
        "provider_hints": ["local"], "status": "READY", "lease": None}), encoding="utf-8")
    jh = JournalHome(tmp_path)
    journal = jh.journal if journal_override is None else journal_override(jh.journal)
    return jh, WorkQueue(items, tmp_path / "ledger.jsonl", journal=journal)


def _execute(jh, accept=True):
    def run(item_id, workspace):
        (workspace / f"{item_id}.txt").write_text("done\n", encoding="utf-8")
        if accept:
            jh.accept(item_id)
        return f"{item_id}.txt"
    return run


def _released(tmp_path):
    path = tmp_path / "ledger.jsonl"
    rows = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
    return [r for r in rows if r.get("type") == "RELEASE"]


def test_real_journal_proof_releases_once_and_restart_does_not_repeat(tmp_path):
    jh, queue = _setup(tmp_path)
    calls = []
    run = _execute(jh)
    first = run_once(queue, HOLDER, "win-host", tmp_path / "w", lambda i, w: calls.append(i) or run(i, w), NOW)
    assert first["outcome"] == "final"
    rel = _released(tmp_path)
    assert len(rel) == 1 and rel[0]["proof"].startswith("journal:") and "RESULT_ACCEPTED|sha256:" in rel[0]["proof"]
    jh.restart()  # controller restart, same courier.db; new queue object on the same ledger
    again = WorkQueue(tmp_path / "items", tmp_path / "ledger.jsonl", journal=jh.journal)
    second = run_once(again, HOLDER, "win-host", tmp_path / "w", lambda i, w: calls.append(i), NOW)
    assert second["outcome"] == "idle" and calls == ["A"] and len(_released(tmp_path)) == 1


def test_missing_journal_result_is_rejected(tmp_path):
    jh, queue = _setup(tmp_path)
    receipt = run_once(queue, HOLDER, "win-host", tmp_path / "w", _execute(jh, accept=False), NOW)
    assert receipt["outcome"] == "blocked" and receipt["reason"] == "RELEASE_REJECTED"
    assert _released(tmp_path) == []


def test_forged_and_tampered_proofs_are_not_proven(tmp_path):
    jh, queue = _setup(tmp_path)
    claim = queue.claim("A", HOLDER, 60, host="win-host", now=NOW)
    real = jh.accept("A")
    tampered = real[:-1] + ("0" if real[-1] != "0" else "1")
    for proof in (*FORGED, tampered, real.replace("journal:", "journal:9")):
        out = queue.release("A", HOLDER, "FINAL", now=NOW, proof=proof)
        assert out["status"] == "NOT_PROVEN", (proof, out)
    assert _released(tmp_path) == [] and claim


def _broken(exc):
    def wrap(journal):
        def boom(*a, **k):
            raise exc
        return View(_journal=journal, events=boom, task=boom)
    return wrap


def test_journal_unavailable_is_safe_rejection_without_exception(tmp_path):
    for exc in (sqlite3.OperationalError("database is locked"), JournalError("closed"), OSError("io")):
        sub = tmp_path / type(exc).__name__
        sub.mkdir()
        jh, queue = _setup(sub, _broken(exc))
        receipt = run_once(queue, HOLDER, "win-host", sub / "w", _execute(jh), NOW)
        assert receipt["outcome"] == "blocked" and receipt["reason"] == "RELEASE_REJECTED"
        assert _released(sub) == []
        proof = journal_release_proof(jh.journal, "A")  # real proof from the healthy journal
        assert proof is not None
        assert check_release_proof(queue.journal, proof, {release_task_id("A")}, 0) == "JOURNAL_UNAVAILABLE"
        assert journal_release_proof(queue.journal, "A") is None
