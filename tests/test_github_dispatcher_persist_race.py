"""M06-01: concurrent persist_packet must admit exactly one winner.

persist_packet() checked path.exists() and then wrote through one shared
tmp path + os.replace. Two admissions racing between the check and the
replace both returned a path, so handle_claimed_task spawned one adapter
per winner for a single dispatch (duplicate external delivery). The fix
claims the final path with O_CREAT|O_EXCL: exactly one winner persists,
losers return None (resume_pending() owns the surviving packet).
"""
import importlib.util
import json
import os
import threading
from pathlib import Path

DISPATCHER = Path(__file__).resolve().parents[1] / "scripts" / "courier_github_dispatcher.py"
IDENTITY = ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")


def load(monkeypatch, tmp_path):
    monkeypatch.setenv("COURIER_API_KEY", "dummy-test-key-not-real")
    monkeypatch.setenv("COURIER_GITHUB_DISPATCH_DIR", str(tmp_path / "dispatch"))
    spec = importlib.util.spec_from_file_location("gh_dispatcher_race_under_test", DISPATCHER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def packet(**over):
    task = {
        "goal_id": "goal-1",
        "task_id": "task-1",
        "attempt_id": "task-1:attempt:1",
        "dispatch_id": "dispatch-" + "b" * 32,
        "worker_id": "GITHUB-DISPATCHER",
        "type": "metadata",
    }
    task.update(over)
    return task


def test_concurrent_persist_admits_single_winner(monkeypatch, tmp_path):
    d = load(monkeypatch, tmp_path)
    gate = threading.Barrier(2)
    real_replace = os.replace

    def gated_replace(src, dst):
        # Force both racers through the old check-then-replace window together.
        if str(dst).endswith(".json") and "dispatch" in str(dst):
            gate.wait(timeout=30)
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", gated_replace)
    results, errors = [], []

    def attempt():
        try:
            results.append(d.persist_packet(packet()))
        except Exception as exc:  # noqa: BLE001 - a racing loser must return None, never raise
            errors.append(exc)

    racers = [threading.Thread(target=attempt) for _ in range(2)]
    for racer in racers:
        racer.start()
    for racer in racers:
        racer.join(timeout=60)
    assert all(not racer.is_alive() for racer in racers)

    assert errors == []
    assert len(results) == 2
    wins = [path for path in results if path is not None]
    assert len(wins) == 1
    stored = json.loads(wins[0].read_text(encoding="utf-8"))
    for field in IDENTITY:
        assert stored[field]
    assert not list((tmp_path / "dispatch").glob("*.tmp"))


def test_sequential_duplicate_persist_stays_single(monkeypatch, tmp_path):
    d = load(monkeypatch, tmp_path)
    first = d.persist_packet(packet())
    assert first is not None and first.is_file()
    assert d.persist_packet(packet()) is None
    stored = json.loads(first.read_text(encoding="utf-8"))
    for field in IDENTITY:
        assert stored[field]
