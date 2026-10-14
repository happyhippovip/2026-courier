"""Concurrent dispatch_intake keeps every record (central-state lock).

Proves: two simultaneous dispatches of distinct intakes both reach the
external call yet both end ADMITTED in central_state.json — no lost update
from interleaved load/save, no shared-tmp collision. Same-intake
concurrency still dispatches externally exactly once.
"""
import importlib.util
import json
import threading
from pathlib import Path

DISPATCHER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "intake_dispatcher.py"


def load_dispatcher(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("intake_dispatcher_locktest", DISPATCHER_PATH)
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(d, "resolve_execution_ref", lambda workflow, since: None)
    monkeypatch.setattr(d, "BIND_ATTEMPTS", 1)
    return d


def write_intake(path, ref):
    path.write_text(json.dumps({"customer_reference": ref, "target_owner": "o",
                                "target_repo": "r", "target_sha": "s"}))


def run_thread(d, path, errors):
    try:
        d.dispatch_intake(str(path))
    except SystemExit as exc:
        errors.append(("exit", exc.code))
    except Exception as exc:  # noqa: BLE001 - surfaced below, never hidden
        errors.append(("error", repr(exc)))


def test_concurrent_distinct_intakes_keep_both_records(tmp_path, monkeypatch):
    d = load_dispatcher(monkeypatch, tmp_path)
    calls = []
    barrier = threading.Barrier(2)

    def fake_run(cmd, **kw):
        calls.append(cmd)
        barrier.wait(timeout=30)  # both external dispatches overlap for real
        class R:
            pass
        return R()

    monkeypatch.setattr(d.subprocess, "run", fake_run)
    fa = tmp_path / "a.json"
    fb = tmp_path / "b.json"
    write_intake(fa, "ref-A")
    write_intake(fb, "ref-B")
    errors = []
    threads = [threading.Thread(target=run_thread, args=(d, p, errors)) for p in (fa, fb)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    assert len(calls) == 2  # both external dispatches happened
    state = json.loads((tmp_path / "central_state.json").read_text())
    assert len(state["tasks"]) == 2
    assert all(t.get("admission") == "ADMITTED" for t in state["tasks"].values())


def test_concurrent_same_intake_dispatches_once(tmp_path, monkeypatch):
    d = load_dispatcher(monkeypatch, tmp_path)
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        class R:
            pass
        return R()

    monkeypatch.setattr(d.subprocess, "run", fake_run)
    fa = tmp_path / "a.json"
    write_intake(fa, "ref-A")
    errors = []
    threads = [threading.Thread(target=run_thread, args=(d, fa, errors)) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert len(calls) == 1  # exactly one external dispatch for one intake
    state = json.loads((tmp_path / "central_state.json").read_text())
    assert len(state["tasks"]) == 1
    assert all(t.get("admission") == "ADMITTED" for t in state["tasks"].values())
