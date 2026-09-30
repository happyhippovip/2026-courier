"""Event-log persistence + crash recovery (desktop overlay, decoupled)."""
import pytest

from courier_desktop import recovery


def event(kind="TASK_COMPLETE", **changes):
    record = {"type": kind, "task_id": "task-1"}
    record.update(changes)
    return record


def test_append_read_roundtrip(tmp_path):
    log = recovery.EventLog(tmp_path / "events.jsonl")
    log.append(event("TASK_ASSIGNED"))
    log.append(event("TASK_COMPLETE", result_id="r-1"))
    events, torn = log.read()
    assert [e["type"] for e in events] == ["TASK_ASSIGNED", "TASK_COMPLETE"]
    assert torn == 0


def test_read_missing_log_is_empty(tmp_path):
    assert recovery.EventLog(tmp_path / "nope.jsonl").read() == ([], 0)


def test_append_rejects_non_dict_and_bad_type(tmp_path):
    log = recovery.EventLog(tmp_path / "e.jsonl")
    with pytest.raises(ValueError):
        log.append(["not", "a", "dict"])
    with pytest.raises(ValueError):
        log.append({"task_id": "task-1"})
    with pytest.raises(ValueError):
        log.append(event(""))


def test_append_rejects_secret_keys(tmp_path):
    log = recovery.EventLog(tmp_path / "e.jsonl")
    with pytest.raises(ValueError, match="secret key"):
        log.append(event("TASK_ASSIGNED", api_key="x"))
    with pytest.raises(ValueError, match="secret key"):
        log.append(event("TASK_ASSIGNED", password="x"))
    assert log.read() == ([], 0)


def test_torn_tail_skipped_and_counted(tmp_path):
    path = tmp_path / "e.jsonl"
    path.write_text('{"type": "A"}\n{"type": "B"}\n{"type": "C", "half": ', encoding="utf-8")
    events, torn = recovery.EventLog(path).read()
    assert [e["type"] for e in events] == ["A", "B"]
    assert torn == 1


def test_middle_corruption_raises(tmp_path):
    path = tmp_path / "e.jsonl"
    path.write_text('{"type": "A"}\nBROKEN\n{"type": "C"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        recovery.EventLog(path).read()


def test_snapshot_roundtrip_and_guards(tmp_path):
    path = tmp_path / "snap.json"
    recovery.save_snapshot(path, {"tasks": ["t-1"]}, 7)
    assert recovery.load_snapshot(path) == ({"tasks": ["t-1"]}, 7)
    with pytest.raises(FileNotFoundError):
        recovery.load_snapshot(tmp_path / "missing.json")
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt snapshot"):
        recovery.load_snapshot(path)
    with pytest.raises(ValueError):
        recovery.save_snapshot(tmp_path / "s2.json", ["not", "dict"], 0)
    with pytest.raises(ValueError):
        recovery.save_snapshot(tmp_path / "s2.json", {}, -1)


def test_recover_replays_only_tail(tmp_path):
    log = recovery.EventLog(tmp_path / "e.jsonl")
    for kind in ("TASK_ASSIGNED", "WORKER_STARTED", "TASK_COMPLETE"):
        log.append(event(kind))
    recovery.save_snapshot(tmp_path / "s.json", {"seen": ["TASK_ASSIGNED"]}, 1)
    seen = []

    def apply(state, ev):
        seen.append(ev["type"])
        state.setdefault("seen", []).append(ev["type"])

    summary = recovery.recover(tmp_path / "e.jsonl", tmp_path / "s.json", apply)
    assert seen == ["WORKER_STARTED", "TASK_COMPLETE"]
    assert summary["replayed"] == 2
    assert summary["torn"] == 0
    assert summary["state"]["seen"] == ["TASK_ASSIGNED", "WORKER_STARTED", "TASK_COMPLETE"]


def test_recover_without_snapshot_starts_fresh(tmp_path):
    log = recovery.EventLog(tmp_path / "e.jsonl")
    log.append(event("TASK_ASSIGNED"))
    summary = recovery.recover(tmp_path / "e.jsonl", tmp_path / "absent.json", lambda s, e: s.update(e))
    assert summary["state"]["type"] == "TASK_ASSIGNED"
    assert summary["snapshot_events"] == 0


def test_recover_truncated_log_raises(tmp_path):
    log = recovery.EventLog(tmp_path / "e.jsonl")
    log.append(event("TASK_ASSIGNED"))
    recovery.save_snapshot(tmp_path / "s.json", {}, 5)
    with pytest.raises(ValueError, match="truncated"):
        recovery.recover(tmp_path / "e.jsonl", tmp_path / "s.json", lambda s, e: None)
