"""Targeted L3 worker-host contract tests (lane L3).

Every test drives real subprocesses, a real file home, or a real local HTTP
stub controller. The L2 compatibility tests append the host's own result
payloads to a real L2 journal. Nothing here touches the live journal, the
network beyond 127.0.0.1, or another lane's files.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

@pytest.fixture(autouse=True)
def windows_teardown_delay():
    yield
    if os.name == "nt":
        time.sleep(0.1)

from courier_worker import host as H
from courier_worker.host import ExecutionSpec, Outcome, WorkerHost
from courier_worker import adapter_bridge as A
from courier_worker import service as S

PY = sys.executable
TOKEN = "test-token"

_FAKES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_fakes")


def _install_adapter_double():
    """Provide the harness ``adapters.synthetic`` double when L4 is absent.

    Lane-local rule: product code must never import L4 source, so this suite
    cannot require it either. When the real ``adapters`` package is importable
    (composed tree) it is used untouched. Otherwise a deterministic double from
    ``tests/_fakes`` is installed for this test only — in ``sys.modules`` for
    in-process bridge validation and on ``PYTHONPATH`` for spawned runner
    subprocesses — and removed afterwards. A missing adapter outside this
    fixture still fails closed with SpecError.
    """
    try:
        import adapters  # noqa: F401 - real L4 present (composed tree)
        return None
    except ImportError:
        pass
    import importlib.util
    pkg_spec = importlib.util.spec_from_file_location(
        "adapters", os.path.join(_FAKES_DIR, "adapters", "__init__.py"),
        submodule_search_locations=[os.path.join(_FAKES_DIR, "adapters")])
    pkg = importlib.util.module_from_spec(pkg_spec)
    sys.modules["adapters"] = pkg
    pkg_spec.loader.exec_module(pkg)
    mod_spec = importlib.util.spec_from_file_location(
        "adapters.synthetic", os.path.join(_FAKES_DIR, "adapters", "synthetic.py"))
    mod = importlib.util.module_from_spec(mod_spec)
    sys.modules["adapters.synthetic"] = mod
    mod_spec.loader.exec_module(mod)
    return ("adapters", "adapters.synthetic")


@pytest.fixture(autouse=True)
def _adapter_double():
    added = _install_adapter_double()
    prev = os.environ.get("PYTHONPATH")
    if added:
        os.environ["PYTHONPATH"] = _FAKES_DIR + (os.pathsep + prev if prev else "")
    try:
        yield
    finally:
        if added:
            for name in added:
                sys.modules.pop(name, None)
            if prev is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = prev


def make_spec(home, name="t1", attempt=1, dispatch="d1", argv=None, **over):
    kw = dict(task_id=name, attempt=attempt, dispatch_id=dispatch, worker_id="w1",
              result_id="r-" + dispatch,
              argv=tuple(argv if argv is not None else [PY, "-c", "pass"]),
              timeout_s=30.0, lease_ttl_s=30.0,
              artifact_dir=os.path.join(str(home), "artifacts", dispatch), heartbeat_s=0.2)
    kw.update(over)
    return ExecutionSpec(**kw)


def make_host(home):
    return WorkerHost(str(home), pressure_probe=lambda: None)


def pgid_dead(pgid):
    try:
        os.killpg(pgid, 0)
        return False
    except (ProcessLookupError, OSError):
        return True


# -- engine: ownership, bounds, cleanup ----------------------------------------

def test_success_collects_artifact_with_exact_ids(tmp_path):
    artifact_dir = tmp_path / "artifacts" / "d1"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "out.txt").write_bytes(b"courier-golden")
    host = make_host(tmp_path)
    spec = make_spec(tmp_path, argv=[PY, "-c", "pass"])
    result = host.run_once(spec)
    assert result.outcome == Outcome.COMPLETED
    assert result.returncode == 0
    assert result.spec.task_id == "t1" and result.spec.attempt == 1
    assert result.spec.dispatch_id == "d1" and result.spec.worker_id == "w1"
    assert result.l2_outcome == "success" and result.retryable is False
    assert (tmp_path / "run" / "claims").exists()
    assert list((tmp_path / "run" / "claims").glob("*.json")) == []
    assert ("out.txt", hashlib.sha256(b"courier-golden").hexdigest()) in [
        (a.path, a.sha256) for a in result.artifacts]
    assert result.wakes <= 3
    assert host.busy is False


def test_second_claim_while_busy_is_refused(tmp_path):
    host = make_host(tmp_path)
    slow = make_spec(tmp_path, dispatch="slow", argv=[PY, "-c", "import time; time.sleep(5)"])
    done = []
    thread = threading.Thread(target=lambda: done.append(host.run_once(slow)), daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not host.busy and time.monotonic() < deadline:
        time.sleep(0.05)
    assert host.busy is True
    with pytest.raises(H.HostBusy):
        host.run_once(make_spec(tmp_path, dispatch="other"))
    thread.join(timeout=15)
    assert done and done[0].outcome == Outcome.COMPLETED
    assert host.busy is False


def test_timeout_kills_whole_tree_within_bound(tmp_path):
    pgid_file = tmp_path / "pgid.txt"
    gpid_file = tmp_path / "gpid.txt"
    # os.getpgid() is POSIX-only; use os.getpid() on Windows so the child
    # survives long enough for the timeout to fire.
    pgid_expr = "os.getpid()" if os.name == "nt" else "os.getpgid(0)"
    child_code = (
        "import os, subprocess, sys, time; "
        "open(r'%s', 'w').write(str(%s)); "
        "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "open(r'%s', 'w').write(str(g.pid)); "
        "time.sleep(30)" % (pgid_file, pgid_expr, gpid_file))
    host = make_host(tmp_path)
    spec = make_spec(tmp_path, argv=[PY, "-c", child_code], timeout_s=2.0, lease_ttl_s=30.0)
    started = time.monotonic()
    result = host.run_once(spec)
    elapsed = time.monotonic() - started
    assert result.outcome == Outcome.TIMEOUT
    assert result.retryable is True
    assert elapsed < 2.0 + H.KILL_GRACE_S + 4.0
    assert result.crash_report_path and os.path.exists(result.crash_report_path)
    if os.name != "nt":
        pgid = int(pgid_file.read_text())
        assert pgid_dead(pgid)
        try:
            os.kill(int(gpid_file.read_text()), 0)
            grandchild_alive = True
        except (ProcessLookupError, OSError):
            grandchild_alive = False
        assert grandchild_alive is False



def test_cancel_terminates_tree_with_truth(tmp_path):
    state = {"cancel": False}

    def arm():
        time.sleep(0.5)
        state["cancel"] = True

    threading.Thread(target=arm, daemon=True).start()
    host = make_host(tmp_path)
    spec = make_spec(tmp_path, argv=[PY, "-c", "import time; time.sleep(30)"],
                     timeout_s=30.0, lease_ttl_s=30.0)
    result = host.run_once(spec, is_cancelled=lambda: state["cancel"])
    assert result.outcome == Outcome.CANCELLED
    assert result.retryable is False
    assert result.l2_outcome == "failure"
    assert result.crash_report_path and os.path.exists(result.crash_report_path)
    assert result.duration_s < 8.0


def test_crash_is_failure_truth_with_report_artifact(tmp_path):
    host = make_host(tmp_path)
    spec = make_spec(tmp_path, argv=[PY, "-c", "import sys; sys.stderr.write('boom'); sys.exit(3)"])
    result = host.run_once(spec)
    assert result.outcome == Outcome.CRASH
    assert result.returncode == 3
    assert result.retryable is False
    assert result.l2_outcome == "failure"
    names = [a.path for a in result.artifacts]
    assert H.CRASH_REPORT_NAME in names
    report = json.loads(open(result.crash_report_path, encoding="utf-8").read())
    assert report["returncode"] == 3 and "boom" in report["stderr_tail"]
    assert report["dispatch_id"] == "d1"


def test_emfile_pauses_once_without_retry(tmp_path, monkeypatch):
    calls = []

    def boom(*args, **kwargs):
        calls.append(1)
        raise OSError(errno.EMFILE, "Too many open files")

    monkeypatch.setattr(subprocess, "Popen", boom)
    host = make_host(tmp_path)
    with pytest.raises(H.ResourcePaused) as exc:
        host.run_once(make_spec(tmp_path))
    assert "fd-exhaustion" in exc.value.reason
    assert len(calls) == 1
    assert host.busy is False


def test_pressure_probe_pauses_before_spawn(tmp_path, monkeypatch):
    calls = []
    real_popen = subprocess.Popen

    def counting(*args, **kwargs):
        calls.append(1)
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", counting)
    host = WorkerHost(str(tmp_path), pressure_probe=lambda: "cpu-pressure: test")
    with pytest.raises(H.ResourcePaused):
        host.run_once(make_spec(tmp_path))
    assert calls == []


@pytest.mark.parametrize("bad", [
    dict(argv=()),
    dict(timeout_s=0),
    dict(timeout_s=H.MAX_TIMEOUT_S + 1),
    dict(lease_ttl_s=0),
    dict(attempt=0),
    dict(task_id=""),
    dict(dispatch_id=""),
])
def test_spec_validation_refusals(tmp_path, bad):
    kw = dict(argv=[PY, "-c", "pass"])
    kw.update(bad)
    with pytest.raises(H.SpecError):
        make_spec(tmp_path, **kw)


def test_orphan_gate_reaps_dead_owner_tree(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX killpg gate; Windows relies on job close semantics")
    proc = subprocess.Popen([PY, "-c", "import time; time.sleep(60)"], start_new_session=True)
    try:
        pgid = os.getpgid(proc.pid)
        record = {"task_id": "t", "attempt": 1, "dispatch_id": "orphan-1", "worker_id": "w",
                  "owner_pid": 2 ** 30, "child_pid": proc.pid, "pgid": pgid}
        claims = tmp_path / "run" / "claims"
        claims.mkdir(parents=True)
        (claims / "dispatch-orphan-1.json").write_text(json.dumps(record), encoding="utf-8")
        assert H.run_orphan_gate(str(tmp_path)) == 1
        assert list(claims.glob("*.json")) == []
        # The "orphan" is this test's own child, so it stays a zombie (and its group
        # stays signalable) until reaped; a real orphan is reaped by init. Reap with a
        # bound: if the gate did not kill the group, this wait times out and fails.
        proc.wait(timeout=10)
        assert pgid_dead(pgid)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_home_lock_second_host_refused(tmp_path):
    fd = H.acquire_home_lock(str(tmp_path))
    try:
        with pytest.raises(H.HostBusy):
            H.acquire_home_lock(str(tmp_path))
    finally:
        H.release_home_lock(fd)
    fd2 = H.acquire_home_lock(str(tmp_path))
    H.release_home_lock(fd2)


def test_lease_expiry_kills_and_reports(tmp_path):
    host = make_host(tmp_path)
    spec = make_spec(tmp_path, argv=[PY, "-c", "import time; time.sleep(30)"],
                     timeout_s=60.0, lease_ttl_s=1.0)
    started = time.monotonic()
    result = host.run_once(spec)
    assert result.outcome == Outcome.LEASE_LOST
    assert result.retryable is True
    assert time.monotonic() - started < 1.0 + H.KILL_GRACE_S + 4.0


def test_wakes_are_bounded(tmp_path):
    beats = []
    host = make_host(tmp_path)
    spec = make_spec(tmp_path, argv=[PY, "-c", "import time; time.sleep(2)"],
                     timeout_s=30.0, lease_ttl_s=30.0, heartbeat_s=0.2)
    result = host.run_once(spec, on_heartbeat=lambda e: beats.append(e))
    assert result.outcome == Outcome.COMPLETED
    quantum = min(spec.heartbeat_s, 1.0)
    assert result.wakes <= int(result.duration_s / quantum) + 3
    assert len(beats) <= result.wakes


def test_outbox_cap_fails_closed(tmp_path):
    outbox = tmp_path / "outbox"
    outbox.mkdir(parents=True)
    for i in range(H.OUTBOX_CAP):
        (outbox / f"old-{i}.json").write_text("{}", encoding="utf-8")
    with pytest.raises(H.OutboxFull):
        H.outbox_write(str(tmp_path), {"dispatch_id": "new-1"})
    same = {"dispatch_id": "old-0"}
    H.outbox_write(str(tmp_path), same)  # same dispatch may refresh


# -- service: wire, delivery, outbox, cancel -----------------------------------

class StubState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.token = TOKEN
        self.claims = []          # queued claim dicts ("EMPTY" for 204)
        self.starts = []
        self.beats = []
        self.results = []         # delivered payloads
        self.result_mode = "accepted"   # accepted | stale | down
        self.sse_plan = []        # payloads to emit on /v1/events


STUB = StubState()


class StubHandler(BaseHTTPRequestHandler):
    server_version = "Stub/1"

    def log_message(self, *args):
        pass

    def _json(self, status, payload=None):
        body = b"" if payload is None else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _auth(self):
        return self.headers.get("X-Courier-Token") == STUB.token

    def do_GET(self):
        if self.path == "/v1/health":
            self._json(200, {"mode": "normal", "head_seq": 0})
        elif self.path == "/v1/events":
            if not self._auth():
                self._json(401)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            try:
                for payload in STUB.sse_plan:
                    time.sleep(0.2)
                    line = ("data: %s\n\n" % json.dumps(payload)).encode()
                    self.wfile.write(line)
                    self.wfile.flush()
                while True:
                    time.sleep(0.2)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
        else:
            self._json(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode()) if body else {}
        except ValueError:
            payload = {}
        if not self._auth():
            self._json(401)
            return
        if self.path == "/v1/claim":
            if STUB.claims and STUB.claims[0] != "EMPTY":
                self._json(200, STUB.claims.pop(0))
            else:
                if STUB.claims:
                    STUB.claims.pop(0)
                self._json(204)
        elif self.path == "/v1/start":
            STUB.starts.append(payload)
            self._json(200, {})
        elif self.path == "/v1/heartbeat":
            STUB.beats.append(payload)
            self._json(200, {})
        elif self.path == "/v1/result":
            STUB.results.append(payload)
            if STUB.result_mode == "stale":
                self._json(409, {"error": "stale"})
            elif STUB.result_mode == "down":
                try:
                    self.connection.shutdown(2)
                except OSError:
                    pass
                self.connection.close()
            else:
                self._json(200, {"status": "ACCEPTED_FOR_VERIFY"})
        else:
            self._json(404)


@pytest.fixture()
def stub():
    STUB.reset()
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def write_token(home):
    run = home / "run"
    run.mkdir(parents=True, exist_ok=True)
    (run / "controller.token").write_text(TOKEN, encoding="utf-8")


EFFECT_KEY = "cfx-" + "a" * 40


def claim_body(dispatch="d1", task="t1", spec_over=None, params=None, attempt=1):
    """The L2 claim shape: a declarative spec, never a command line."""
    spec = {"adapter": "synthetic", "effect_class": "idempotent", "timeout_s": 30,
            "effect_key": EFFECT_KEY,
            "params": {"sleep_s": 0, "write": "out.txt", "content": "courier-golden", **(params or {})}}
    spec.update(spec_over or {})
    return {"task_id": task, "attempt": attempt, "dispatch_id": dispatch, "ttl_s": 30, "spec": spec}


def test_claim_start_result_wire_exact_ids(tmp_path, stub):
    write_token(tmp_path)
    STUB.claims.append(claim_body())
    loop = S.WorkerLoop(str(tmp_path), stub, "w1", 0.2)
    assert loop.iterate(threading.Event()) == "delivered"
    assert STUB.starts == [{"dispatch_id": "d1"}]
    assert len(STUB.results) == 1
    payload = STUB.results[0]
    assert payload["dispatch_id"] == "d1" and payload["result_id"] == "r-d1"
    assert payload["outcome"] == "success" and "retryable" not in payload
    digest = hashlib.sha256(b"courier-golden").hexdigest()
    assert payload["artifacts"] == [{"path": "artifacts/d1/out.txt", "sha256": digest}]
    assert (tmp_path / "artifacts" / "d1" / "out.txt").read_bytes() == b"courier-golden"
    assert H.outbox_read_all(str(tmp_path)) == []
    assert not (tmp_path / "run" / "requests" / "d1.json").exists()  # bridge files cleaned up
    assert all(b["dispatch_ids"] == ["d1"] for b in STUB.beats)


def _crash_payload(tmp_path):
    host = make_host(tmp_path)
    spec = make_spec(tmp_path, argv=[PY, "-c", "import sys; sys.exit(2)"])
    result = host.run_once(spec)
    assert result.outcome == Outcome.CRASH
    payload = S.build_result_payload(result)
    assert payload["outcome"] == "failure" and payload["retryable"] is False
    return payload


def test_result_payload_passes_l2_validation(tmp_path):
    events_mod = pytest.importorskip("courier_core.events")
    Event, EventType = events_mod.Event, events_mod.EventType
    payload = _crash_payload(tmp_path)
    for event in (
            Event(type=EventType.TASK_CREATED, task_id="t1",
                  payload={"adapter": "synthetic", "params": {}, "effect_class": "idempotent",
                           "max_attempts": 3, "lease_ttl_s": 30}),
            Event(type=EventType.TASK_CLAIMED, task_id="t1", attempt=1,
                  dispatch_id="d1", worker_id="w1", payload={"ttl_s": 30}),
            Event(type=EventType.TASK_STARTED, task_id="t1", attempt=1,
                  dispatch_id="d1", worker_id="w1"),
            Event(type=EventType.RESULT_READY, task_id="t1", attempt=1,
                  dispatch_id=payload["dispatch_id"], worker_id="w1",
                  result_id=payload["result_id"],
                  payload={"artifacts": payload["artifacts"], "outcome": payload["outcome"]})):
        events_mod.validate(event)  # raises on any contract deviation


@pytest.mark.skipif(sys.version_info < (3, 10),
                    reason="L2 projection uses zip(strict), 3.10+; graded CI runs 3.12")
def test_result_payload_journals_clean_in_real_l2(tmp_path):
    journal_mod = pytest.importorskip("courier_core.journal")
    from courier_core.events import Event, EventType

    payload = _crash_payload(tmp_path)

    journal = journal_mod.Journal(str(tmp_path / "courier.db")).open()
    try:
        journal.append(Event(type=EventType.TASK_CREATED, task_id="t1",
                             payload={"adapter": "synthetic", "params": {},
                                      "effect_class": "idempotent",
                                      "max_attempts": 3, "lease_ttl_s": 30}))
        journal.append(Event(type=EventType.TASK_CLAIMED, task_id="t1", attempt=1,
                             dispatch_id="d1", worker_id="w1", payload={"ttl_s": 30}))
        journal.append(Event(type=EventType.TASK_STARTED, task_id="t1", attempt=1,
                             dispatch_id="d1", worker_id="w1"))
        journal.append(Event(type=EventType.RESULT_READY, task_id="t1", attempt=1,
                             dispatch_id=payload["dispatch_id"], worker_id="w1",
                             result_id=payload["result_id"],
                             payload={"artifacts": payload["artifacts"],
                                      "outcome": payload["outcome"]}))
        journal.append(Event(type=EventType.RESULT_ACCEPTED, task_id="t1", attempt=1,
                             dispatch_id="d1", result_id=payload["result_id"]))
        journal.append(Event(type=EventType.TASK_COMPLETE, task_id="t1", attempt=1,
                             dispatch_id="d1", result_id=payload["result_id"]))
        report = journal.verify_chain()
        assert report.ok
        state = journal.task("t1")
        assert state is not None and state.status.value == "COMPLETE"
    finally:
        journal.close()


def test_409_drops_outbox_without_resend(tmp_path, stub):
    write_token(tmp_path)
    STUB.claims.append(claim_body())
    STUB.result_mode = "stale"
    loop = S.WorkerLoop(str(tmp_path), stub, "w1", 0.2)
    assert loop.iterate(threading.Event()) == "delivered"
    assert len(STUB.results) == 1
    assert H.outbox_read_all(str(tmp_path)) == []
    assert loop.flush_outbox() == 0
    assert len(STUB.results) == 1


def test_controller_down_keeps_outbox_then_flushes_identical(tmp_path, stub):
    write_token(tmp_path)
    STUB.claims.append(claim_body())
    STUB.result_mode = "down"
    loop = S.WorkerLoop(str(tmp_path), stub, "w1", 0.2)
    assert loop.iterate(threading.Event()) == "delivered"
    pending = H.outbox_read_all(str(tmp_path))
    assert len(pending) == 1
    kept = pending[0][1]
    STUB.result_mode = "accepted"
    assert loop.flush_outbox() == 0
    assert H.outbox_read_all(str(tmp_path)) == []
    assert len(STUB.results) == 2  # one failed attempt recorded, one delivered
    assert STUB.results[-1] == kept


def test_no_resend_after_accept(tmp_path, stub):
    write_token(tmp_path)
    STUB.claims.append(claim_body())
    loop = S.WorkerLoop(str(tmp_path), stub, "w1", 0.2)
    assert loop.iterate(threading.Event()) == "delivered"
    assert loop.flush_outbox() == 0
    assert len(STUB.results) == 1


def test_sse_cancel_aborts_run_promptly(tmp_path, stub):
    write_token(tmp_path)
    STUB.claims.append(claim_body(task="t9", dispatch="d9", params={"hang": True}))
    STUB.sse_plan.append({"type": "TASK_CANCEL_REQUESTED", "task_id": "t9"})
    loop = S.WorkerLoop(str(tmp_path), stub, "w1", 0.2)
    started = time.monotonic()
    assert loop.iterate(threading.Event()) == "delivered"
    assert time.monotonic() - started < 8.0
    assert len(STUB.results) == 1
    assert STUB.results[0]["outcome"] == "failure"
    assert STUB.results[0]["retryable"] is False
    assert {"dispatch_ids": [], "worker_id": "w1"} in STUB.beats  # stop confirmation


def test_stop_releases_blocked_stream(tmp_path, stub):
    # A silent SSE stream must not pin the socket and the watcher thread for
    # timeout_s after the run ends (that was the Windows golden handle leak).
    watcher = S.CancelWatcher(stub, TOKEN, "t-quiet", timeout_s=30.0)
    watcher.start()
    time.sleep(1.0)  # subscribed and waiting on the silent stream
    thread = watcher._thread
    assert thread.is_alive()
    started = time.monotonic()
    watcher.stop()
    assert time.monotonic() - started < 1.5
    assert not thread.is_alive()
    assert not watcher.degraded


def test_sse_rejected_subscription_degrades(tmp_path, stub, monkeypatch):
    monkeypatch.setattr(S, "SSE_RECONNECTS", 0)
    watcher = S.CancelWatcher(stub, "wrong-token", "t-x", timeout_s=5.0)
    watcher.start()
    deadline = time.monotonic() + 5
    while not watcher.degraded and time.monotonic() < deadline:
        time.sleep(0.05)
    watcher.stop()
    assert watcher.degraded and not watcher.cancelled()


@pytest.mark.parametrize("spec_over, params, needle", [
    ({"argv": [PY, "-c", "import os; os.system('echo pwned')"]}, None, "argv"),
    ({"adapter": "shell"}, None, "not allowlisted"),
    ({"adapter": "courier_worker.adapter_runner"}, None, "not allowlisted"),
    ({"adapter": None}, None, "not allowlisted"),
    ({"params": "sleep 1"}, None, "params must be an object"),
    ({}, {"write": "../escape.txt"}, "synthetic params rejected"),
    ({}, {"write": "/etc/passwd"}, "synthetic params rejected"),
    ({}, {"sleep_s": -1}, "synthetic params rejected"),
    ({}, {"hang": "yes"}, "synthetic params rejected"),
    ({"effect_key": "bad key; rm"}, None, "effect_key"),
    ({"effect_key": None}, None, "effect_key"),
])
def test_untrusted_specs_are_refused_before_start(tmp_path, stub, spec_over, params, needle):
    write_token(tmp_path)
    STUB.claims.append(claim_body(spec_over=spec_over, params=params))
    loop = S.WorkerLoop(str(tmp_path), stub, "w1", 0.2)
    assert loop.iterate(threading.Event()) == "spec-rejected"
    assert STUB.starts == []  # nothing started, nothing spawned
    payload = STUB.results[0]
    assert payload["outcome"] == "failure" and payload["retryable"] is False
    assert needle in payload["reason"]
    assert not (tmp_path / "artifacts").exists() or not any((tmp_path / "artifacts").iterdir())
    assert not (tmp_path.parent / "escape.txt").exists()


def test_transient_adapter_failure_is_a_retryable_failure(tmp_path, stub):
    write_token(tmp_path)
    STUB.claims.append(claim_body(params={"fail_transient_n": 1}))
    loop = S.WorkerLoop(str(tmp_path), stub, "w1", 0.2)
    assert loop.iterate(threading.Event()) == "delivered"
    payload = STUB.results[0]
    assert payload["outcome"] == "failure" and payload["retryable"] is True
    assert payload["reason"] == "synthetic transient fault" and payload["artifacts"] == []


def test_synthetic_crash_is_non_retryable_failure_with_report(tmp_path, stub):
    write_token(tmp_path)
    STUB.claims.append(claim_body(params={"crash_after_s": 0}))
    loop = S.WorkerLoop(str(tmp_path), stub, "w1", 0.2)
    assert loop.iterate(threading.Event()) == "delivered"
    payload = STUB.results[0]
    assert payload["outcome"] == "failure" and payload["retryable"] is False
    assert payload["artifacts"][0]["path"] == "artifacts/d1/" + H.CRASH_REPORT_NAME
    report = json.loads((tmp_path / "artifacts" / "d1" / H.CRASH_REPORT_NAME).read_text())
    assert report["returncode"] == 3 and "crashed" in report["stderr_tail"]


def test_fault_only_on_listed_attempts(tmp_path, stub):
    write_token(tmp_path)
    STUB.claims.append(claim_body(attempt=2, params={"crash_after_s": 0, "fault_attempts": [1]}))
    loop = S.WorkerLoop(str(tmp_path), stub, "w1", 0.2)
    assert loop.iterate(threading.Event()) == "delivered"
    assert STUB.results[0]["outcome"] == "success"


def test_exit_zero_without_report_is_never_success(tmp_path):
    host = make_host(tmp_path)
    spec = S.resolve_spec(claim_body(), "w1", str(tmp_path / "artifacts"), 0.2, home=str(tmp_path))
    spec = ExecutionSpec(**{**spec.__dict__, "argv": (PY, "-c", "pass")})  # exits 0, writes nothing
    result = host.run_once(spec)
    assert result.outcome == Outcome.COMPLETED
    payload = S.build_result_payload(result, None, home=str(tmp_path))
    assert payload["outcome"] == "failure" and payload["retryable"] is False
    assert "no structured result" in payload["reason"]


def test_bridge_request_preserves_identity_and_effect_key(tmp_path):
    spec = S.resolve_spec(claim_body(dispatch="dsp-7", task="t7", attempt=3), "w1",
                          str(tmp_path / "artifacts"), 0.2, home=str(tmp_path))
    assert spec.argv == (sys.executable, A.RUNNER_SCRIPT, A.request_path(str(tmp_path), "dsp-7"))
    assert (spec.task_id, spec.attempt, spec.dispatch_id, spec.effect_key) == ("t7", 3, "dsp-7", EFFECT_KEY)
    path = A.write_request(str(tmp_path), spec)
    request = json.loads(open(path, encoding="utf-8").read())
    assert request["effect_key"] == EFFECT_KEY and request["attempt"] == 3
    assert request["task_id"] == "t7" and request["dispatch_id"] == "dsp-7"
    assert request["workdir"] == os.path.join(str(tmp_path), "artifacts", "dsp-7")


def test_runner_refuses_a_non_allowlisted_request(tmp_path):
    request = tmp_path / "req.json"
    request.write_text(json.dumps({"adapter": "os", "params": {}, "attempt": 1,
                                   "workdir": str(tmp_path / "w"), "report": str(tmp_path / "r.json")}))
    proc = subprocess.run([PY, A.RUNNER_SCRIPT, str(request)], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 2 and "not allowlisted" in proc.stderr
    assert not (tmp_path / "r.json").exists() and not (tmp_path / "w").exists()


def test_missing_adapter_fails_closed_with_spec_error(monkeypatch):
    """No real L4 and no double importable: validate_request must refuse."""
    monkeypatch.setitem(sys.modules, "adapters", None)
    monkeypatch.setitem(sys.modules, "adapters.synthetic", None)
    with pytest.raises(A.SpecError, match="adapter implementation unavailable"):
        A.validate_request(claim_body()["spec"])


def test_cli_module_entry_rejects_parallel(tmp_path):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run(
        [PY, "-m", "courier_worker.host", "--max-tasks", "2",
         "--controller", "http://127.0.0.1:9", "--home", str(tmp_path)],
        cwd=repo_root, env={**os.environ, "PYTHONPATH": repo_root},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    assert proc.returncode == 2


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object containment")
def test_job_object_kills_tree_on_terminate(tmp_path):
    import psutil

    me = psutil.Process()
    before = {p.pid for p in me.children(recursive=True)}
    host = make_host(tmp_path)
    grandchild_code = ("import subprocess, sys, time; "
                       "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                       "import time as _t; _t.sleep(60)")
    spec = make_spec(tmp_path, argv=[PY, "-c", grandchild_code],
                     timeout_s=60.0, lease_ttl_s=60.0)
    stop = threading.Event()

    def arm():
        time.sleep(1.0)
        stop.set()

    threading.Thread(target=arm, daemon=True).start()
    result = host.run_once(spec, is_cancelled=stop.is_set)
    assert result.outcome == Outcome.CANCELLED
    leftovers = [p.pid for p in me.children(recursive=True) if p.pid not in before]
    assert leftovers == []

