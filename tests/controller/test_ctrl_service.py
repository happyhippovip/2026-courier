"""L2 controller over real HTTP: boot, auth, SSE, shutdown, concurrency.

In-process LiveService for API behaviour; real `python -m courier_core.serve`
subprocesses for the process contract (CLI, lock, token file, signals, exit).
"""

import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import requests

from ctrl_helpers import LiveService, Verifiers, accept_all, result_body, task_body

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def live(tmp_path):
    service = LiveService(tmp_path / "home")
    yield service
    service.stop()


def sse_ids(live, last_event_id, until_seq, timeout=10):
    ids = []
    deadline = time.monotonic() + timeout
    with live.session.get(live.base + "/v1/events", headers={"Last-Event-ID": str(last_event_id)},
                          stream=True, timeout=(5, 2)) as response:
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("text/event-stream")
        try:
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith("id:"):
                    ids.append(int(line[3:].strip()))
                    if ids[-1] >= until_seq:
                        break
                if time.monotonic() > deadline:
                    break
        except requests.exceptions.ConnectionError:
            pass
    return ids


def journal_seqs(home):
    conn = sqlite3.connect(Path(home, "courier.db").resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return [row[0] for row in conn.execute("SELECT seq FROM events ORDER BY seq")]
    finally:
        conn.close()


def golden_over_http(live):
    task_id = live.post("/v1/tasks", task_body()).json()["task_id"]
    lease = live.post("/v1/claim", {"worker_id": "w1"}).json()
    assert live.post("/v1/start", {"dispatch_id": lease["dispatch_id"]}).status_code == 200
    answer = live.post("/v1/result", result_body(lease["dispatch_id"]))
    assert answer.status_code == 200 and answer.json()["status"] == "ACCEPTED_FOR_VERIFY"
    deadline = time.monotonic() + 10
    while live.get(f"/v1/tasks/{task_id}").json()["status"] != "COMPLETE":
        assert time.monotonic() < deadline, "verification did not complete"
        time.sleep(0.05)
    return task_id, lease


# --------------------------------------------------------------- A + B
def test_health_and_localhost_only_binding(live):
    health = live.get("/v1/health").json()
    assert health["mode"] == "normal" and health["head_seq"] >= 1
    assert live.service.server.server_address[0] == "127.0.0.1"


@pytest.mark.parametrize("headers", [{}, {"X-Courier-Token": "wrong"}, {"X-Courier-Token": ""}])
def test_missing_or_wrong_token_is_rejected_without_leaking(live, headers):
    for method, path in (("GET", "/v1/health"), ("POST", "/v1/tasks"), ("GET", "/v1/events")):
        response = requests.request(method, live.base + path, headers=headers, json=task_body(), timeout=10)
        assert response.status_code == 401
        assert live.service.token not in response.text
    assert live.controller.journal.tasks() == []


def test_token_file_is_private_and_stable(tmp_path):
    home = tmp_path / "home"
    first = LiveService(home)
    token = first.service.token
    first.stop()
    second = LiveService(home)
    try:
        assert second.service.token == token
        if os.name != "nt":
            assert (home / "run" / "controller.token").stat().st_mode & 0o077 == 0
    finally:
        second.stop()


def test_errors_are_json_and_bounded(live):
    assert live.post("/v1/nope").status_code == 404
    assert live.session.put(live.base + "/v1/tasks", timeout=10).status_code == 405
    bad = live.session.post(live.base + "/v1/tasks", data=b"{not json", timeout=10,
                            headers={"Content-Type": "application/json"})
    assert bad.status_code == 400 and bad.json()["error"] == "invalid_json"
    huge = live.session.post(live.base + "/v1/tasks", data=b"x" * (1024 * 1024 + 1), timeout=10)
    assert huge.status_code == 413


def test_connection_is_closed_when_a_body_cannot_be_trusted(live):
    import socket
    for raw in (b"POST /v1/tasks HTTP/1.1\r\nHost: x\r\nX-Courier-Token: wrong\r\nContent-Length: 2\r\n\r\n{}",
                b"POST /v1/tasks HTTP/1.1\r\nHost: x\r\nX-Courier-Token: " + live.service.token.encode()
                + b"\r\nContent-Length: abc\r\n\r\n"):
        with socket.create_connection(("127.0.0.1", live.service.port), timeout=5) as sock:
            sock.sendall(raw)
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break  # server closed the connection
                data += chunk
            assert data.split(b"\r\n", 1)[0] in (b"HTTP/1.1 401 Unauthorized", b"HTTP/1.1 411 Length Required")


def test_golden_sequence_over_http(live):
    task_id, _ = golden_over_http(live)
    events = [e for e in live.controller.events_after(0) if e.task_id == task_id]
    assert [e.type.value for e in events] == ["TASK_CREATED", "TASK_CLAIMED", "TASK_STARTED", "RESULT_READY",
                                              "RESULT_ACCEPTED", "TASK_COMPLETE"]
    assert live.post("/v1/claim", {"worker_id": "w1"}).status_code == 204


def test_duplicate_and_stale_results_over_http(live):
    _, lease = golden_over_http(live)
    head = live.get("/v1/health").json()["head_seq"]
    dup = live.post("/v1/result", result_body(lease["dispatch_id"]))
    assert dup.status_code == 200 and dup.json()["status"] == "ACK_DUPLICATE"
    stale = live.post("/v1/result", result_body(lease["dispatch_id"], result_id="other"))
    assert stale.status_code == 409
    assert live.get("/v1/health").json()["head_seq"] == head + 1  # exactly one LATE_RESULT_DISCARDED


# ------------------------------------------------------------------ K. SSE
def test_sse_ids_are_journal_seqs_and_resume_is_exact(live):
    golden_over_http(live)
    seqs = journal_seqs(live.service.home)
    assert sse_ids(live, 0, seqs[-1]) == seqs
    middle = seqs[len(seqs) // 2]
    assert sse_ids(live, middle, seqs[-1]) == [s for s in seqs if s > middle]


def test_sse_streams_live_events_without_duplicates(live):
    start = journal_seqs(live.service.home)[-1]
    collected = []
    reader = threading.Thread(target=lambda: collected.extend(sse_ids(live, start, start + 3, timeout=15)))
    reader.start()
    time.sleep(0.3)
    for _ in range(3):
        live.post("/v1/tasks", task_body())
    reader.join(20)
    assert collected == [start + 1, start + 2, start + 3]


def test_sse_payload_is_the_journal_row(live):
    golden_over_http(live)
    with live.session.get(live.base + "/v1/events", headers={"Last-Event-ID": "0"}, stream=True,
                          timeout=(5, 2)) as response:
        lines = []
        for line in response.iter_lines(decode_unicode=True):
            lines.append(line)
            if len(lines) > 3:
                break
    data = json.loads(next(line for line in lines if line.startswith("data:"))[5:])
    assert data["seq"] == 1 and data["type"] == "CONTROLLER_STARTED" and len(data["hash"]) == 64


def test_sse_rejects_bad_last_event_id(live):
    response = live.get("/v1/events", headers={"Last-Event-ID": "abc"})
    assert response.status_code == 400


# ---------------------------------------------------------- N. concurrency
@pytest.mark.parametrize("round_", range(10))
def test_exactly_one_claimant_under_contention(live, round_):
    live.post("/v1/tasks", task_body())
    barrier = threading.Barrier(12)
    answers = []

    def claimer(n):
        session = requests.Session()
        session.headers["X-Courier-Token"] = live.service.token
        barrier.wait()
        answers.append(session.post(live.base + "/v1/claim", json={"worker_id": f"w{n}"}, timeout=15).status_code)

    threads = [threading.Thread(target=claimer, args=(n,)) for n in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert sorted(answers) == [200] + [204] * 11


@pytest.mark.parametrize("round_", range(10))
def test_concurrent_duplicate_results_record_one_effect(live, round_):
    live.post("/v1/tasks", task_body())
    lease = live.post("/v1/claim", {"worker_id": "w1"}).json()
    live.post("/v1/start", {"dispatch_id": lease["dispatch_id"]})
    barrier = threading.Barrier(8)
    answers = []

    def poster():
        session = requests.Session()
        session.headers["X-Courier-Token"] = live.service.token
        barrier.wait()
        answers.append(session.post(live.base + "/v1/result", json=result_body(lease["dispatch_id"]),
                                    timeout=15).json()["status"])

    threads = [threading.Thread(target=poster) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert sorted(answers) == ["ACCEPTED_FOR_VERIFY"] + ["ACK_DUPLICATE"] * 7
    ready = [e for e in live.controller.events_after(0, 10_000)
             if e.type.value == "RESULT_READY" and e.dispatch_id == lease["dispatch_id"]]
    assert len(ready) == 1


def test_busy_controller_answers_503_instead_of_hanging(tmp_path):
    from courier_core.controller import ApiError, Controller
    ctl = Controller(tmp_path / "home", verifier=Verifiers(probe=accept_all), lock_timeout_s=0.3).boot()
    try:
        held = threading.Event()
        release = threading.Event()

        def hog():
            with ctl._locked():
                held.set()
                release.wait(5)

        thread = threading.Thread(target=hog)
        thread.start()
        held.wait(5)
        started = time.monotonic()
        with pytest.raises(ApiError) as info:
            ctl.create_task(task_body())
        assert info.value.status == 503 and time.monotonic() - started < 2
        release.set()
        thread.join(5)
        assert ctl.create_task(task_body())[0] == 201
    finally:
        ctl.stop()


def test_external_sqlite_writer_only_delays_a_write(live):
    conn = sqlite3.connect(str(live.service.home / "courier.db"), timeout=5, isolation_level=None)
    conn.execute("BEGIN IMMEDIATE")
    try:
        result = {}
        thread = threading.Thread(target=lambda: result.update(r=live.post("/v1/tasks", task_body(), timeout=40)))
        thread.start()
        time.sleep(1.0)
        assert thread.is_alive()  # waiting on SQLite's finite busy timeout, not failing
    finally:
        conn.execute("ROLLBACK")
        conn.close()
    thread.join(40)
    assert result["r"].status_code == 201


# ------------------------------------------------- process contract (A, M)
def _spawn(home, *extra, env_home=False, port=0):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT), env.get("PYTHONPATH", "")])
    args = [sys.executable, "-m", "courier_core.serve", "--port", str(port), "--print-port", *extra]
    if env_home:
        env["COURIER_HOME"] = str(home)
    else:
        args += ["--home", str(home)]
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
    return subprocess.Popen(args, cwd=str(REPO_ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, **kwargs)


def _port_of(proc):
    line = proc.stdout.readline().strip()
    assert line.isdigit(), (line, proc.stderr.read() if proc.poll() is not None else "")
    return int(line)


def _session(home):
    session = requests.Session()
    session.headers["X-Courier-Token"] = (Path(home) / "run" / "controller.token").read_text().strip()
    return session


def test_process_boot_shutdown_and_clean_close(tmp_path):
    home = tmp_path / "home"
    proc = _spawn(home, env_home=True)
    try:
        port = _port_of(proc)
        session = _session(home)
        assert session.get(f"http://127.0.0.1:{port}/v1/health", timeout=10).json()["mode"] == "normal"
        assert session.post(f"http://127.0.0.1:{port}/v1/shutdown", timeout=10).status_code == 200
        assert proc.wait(timeout=10) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
    _, stderr = proc.communicate(timeout=10)
    assert session.headers["X-Courier-Token"] not in stderr
    conn = sqlite3.connect(str(home / "courier.db"))
    types_ = [row[0] for row in conn.execute("SELECT type FROM events ORDER BY seq")]
    conn.close()
    assert types_ == ["CONTROLLER_STARTED", "CONTROLLER_STOPPED"]
    assert not Path(str(home / "courier.db") + "-wal").exists() or \
        Path(str(home / "courier.db") + "-wal").stat().st_size == 0


def test_one_controller_per_home(tmp_path):
    home = tmp_path / "home"
    first = _spawn(home)
    try:
        _port_of(first)
        second = _spawn(home)
        assert second.wait(timeout=20) != 0
        assert "another Courier controller" in second.stderr.read()
    finally:
        first.kill()
        first.wait(timeout=10)


@pytest.mark.skipif(os.name == "nt", reason="POSIX signal path; Windows uses CTRL_BREAK (tested by the golden harness)")
def test_sigterm_is_a_graceful_stop(tmp_path):
    home = tmp_path / "home"
    proc = _spawn(home)
    _port_of(proc)
    proc.send_signal(signal.SIGTERM)
    assert proc.wait(timeout=10) == 0


def test_restarted_controller_rebinds_the_same_port(tmp_path):
    """Golden restart contract: graceful stop or hard kill, then a new controller on the same port."""
    home = tmp_path / "home"
    proc = _spawn(home)
    port = _port_of(proc)
    session = _session(home)
    session.post(f"http://127.0.0.1:{port}/v1/tasks", json=task_body(), timeout=10)
    session.post(f"http://127.0.0.1:{port}/v1/shutdown", timeout=10)
    assert proc.wait(timeout=10) == 0
    proc = _spawn(home, port=port)
    try:
        assert _port_of(proc) == port
        assert session.get(f"http://127.0.0.1:{port}/v1/health", timeout=10).json()["mode"] == "normal"
        proc.kill()
        proc.wait(timeout=10)
        proc = _spawn(home, port=port)
        assert _port_of(proc) == port
        assert session.get(f"http://127.0.0.1:{port}/v1/health", timeout=10).json()["mode"] == "normal"
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_process_listens_on_loopback_only(tmp_path):
    home = tmp_path / "home"
    proc = _spawn(home)
    try:
        port = _port_of(proc)
        if sys.platform.startswith("linux"):
            listening = Path("/proc/net/tcp").read_text().splitlines()[1:]
            mine = [line.split() for line in listening if line.split()[1].endswith(f":{port:04X}")
                    and line.split()[3] == "0A"]
            assert mine and all(entry[1].split(":")[0] == "0100007F" for entry in mine), mine
        import socket
        candidates = {info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
        for address in candidates - {"127.0.0.1"}:
            with socket.socket() as probe:
                probe.settimeout(2)
                assert probe.connect_ex((address, port)) != 0, f"reachable on {address}"
    finally:
        proc.kill()
        proc.wait(timeout=10)


# ------------------------------------------------- M. cancel/resolve routes
def test_cancel_route_over_http(live):
    """Cancel was only pinned in-process: the wire path (regex + body shape)
    needs its own pin, since automation cancels stuck claims over HTTP."""
    task_id = live.post("/v1/tasks", task_body()).json()["task_id"]
    answer = live.post(f"/v1/tasks/{task_id}/cancel")
    assert answer.status_code == 200 and answer.json()["status"] == "CANCELLED"
    assert live.get(f"/v1/tasks/{task_id}").json()["status"] == "CANCELLED"
    repeat = live.post("/v1/tasks/task-unknown/cancel")
    assert repeat.status_code == 404
    terminal = live.post(f"/v1/tasks/{task_id}/cancel")
    assert terminal.status_code == 409  # terminal tasks stay decided


def test_resolve_route_validates_over_http(live):
    """Resolve validation (decision/actor/attempt/reason, then task lookup)
    must hold over HTTP before any human-desk flow can rely on it."""
    task_id = live.post("/v1/tasks", task_body()).json()["task_id"]
    bad = live.post(f"/v1/tasks/{task_id}/resolve",
                    {"decision": "bogus", "actor": "desk:ana", "attempt": 1, "reason": "x"})
    assert bad.status_code == 400
    queued = live.post(f"/v1/tasks/{task_id}/resolve",
                       {"decision": "retry_authorized", "actor": "desk:ana", "attempt": 1,
                        "reason": "operator retry"})
    assert queued.status_code == 409  # only a blocked task takes a decision
    missing = live.post("/v1/tasks/task-unknown/resolve",
                        {"decision": "retry_authorized", "actor": "desk:ana", "attempt": 1,
                         "reason": "operator retry"})
    assert missing.status_code == 404


def test_newest_event_reaches_a_block_buffered_client_before_the_stream_idles(live):
    # requests.iter_lines reads 512-byte blocks; without the idle padding a short
    # final event sat in the client's buffer until the 15 s keepalive.
    task_id = live.post("/v1/tasks", task_body()).json()["task_id"]
    head = journal_seqs(live.service.home)[-1]
    started = time.monotonic()
    assert sse_ids(live, head - 1, head, timeout=5) == [head]
    assert time.monotonic() - started < 2
    assert live.get(f"/v1/tasks/{task_id}").status_code == 200
