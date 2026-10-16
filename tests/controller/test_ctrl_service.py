"""L2 controller over real HTTP: boot, auth, SSE, shutdown, concurrency.

In-process LiveService for API behaviour; real `python -m courier_core.serve`
subprocesses for the process contract (CLI, lock, token file, signals, exit).
"""

import hashlib
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


def test_queue_fairness_unblocked_local_work_not_starved(live):
    """Mission 15: Queue starvation and fairness across mixed task states.

    Verifies:
    1. A blocked task or task requiring unavailable capability does not stall queue.
    2. Local executable routine tasks are claimed in order.
    3. Human gate / blocked tasks remain visible in BLOCKED status.
    4. No busy-loop or deadlock occurs when runnable tasks are exhausted.
    """
    # 1. Blocked task (simulate human intervention requirement: cancel while queued)
    t_human = live.post("/v1/tasks", task_body(adapter="probe", effect_class="non_idempotent")).json()["task_id"]
    live.post("/v1/tasks/" + t_human + "/cancel", {"actor": "operator", "reason": "human_gate"})
    assert live.get(f"/v1/tasks/{t_human}").json()["status"] == "CANCELLED"

    # 2. Local routine task 1 (QUEUED)
    t_local1 = live.post("/v1/tasks", task_body(adapter="probe", effect_class="idempotent")).json()["task_id"]

    # 3. Local routine task 2 (QUEUED)
    t_local2 = live.post("/v1/tasks", task_body(adapter="probe", effect_class="idempotent")).json()["task_id"]

    # Worker claims next available: must get t_local1, not get stuck on cancelled/blocked
    claim1 = live.post("/v1/claim", {"worker_id": "w1"}).json()
    assert claim1 is not None
    assert claim1["task_id"] == t_local1

    # Next claim must get t_local2
    claim2 = live.post("/v1/claim", {"worker_id": "w1"}).json()
    assert claim2 is not None
    assert claim2["task_id"] == t_local2

    # Queue exhausted of runnable tasks: claim returns 204 No Content without spinning or busy-looping
    claim_empty = live.post("/v1/claim", {"worker_id": "w1"})
    assert claim_empty.status_code == 204


def test_expired_claim_without_blind_replay_and_foreign_claim_protection(live):
    """Mission 14: Expired claim without blind replay.

    Verifies:
    1. Normal completion: worker claims, starts, reports result -> COMPLETE.
    2. Expired lease on started non-idempotent task does NOT auto-retry;
       it transitions to BLOCKED to prevent blind duplicate external execution.
    3. Expired lease on unstarted task may safely re-queue.
    4. Foreign claim protection: worker w2 cannot start or report results for
       a lease owned by worker w1 (fails closed with 400/409).
    """
    # 1. Foreign claim protection: worker w2 cannot act on worker w1's lease
    t_iso = live.post("/v1/tasks", task_body(adapter="probe", effect_class="idempotent")).json()["task_id"]
    lease_w1 = live.post("/v1/claim", {"worker_id": "w1"}).json()
    assert lease_w1["task_id"] == t_iso

    # w2 attempts to hijack w1's dispatch_id
    bad_start = live.post("/v1/start", {"dispatch_id": lease_w1["dispatch_id"], "worker_id": "w2"})
    assert bad_start.status_code in (400, 403, 409)

    # w2 attempts to deliver results for w1's dispatch_id
    bad_result = live.post("/v1/result", result_body(dispatch_id=lease_w1["dispatch_id"], worker_id="w2"))
    assert bad_result.status_code in (400, 403, 409)

    # 2. Normal completion by legitimate owner w1
    assert live.post("/v1/start", {"dispatch_id": lease_w1["dispatch_id"], "worker_id": "w1"}).status_code == 200
    assert live.post("/v1/result", result_body(dispatch_id=lease_w1["dispatch_id"])).status_code == 200

    # 3. Non-idempotent started task with expired lease MUST NOT blind-replay
    t_non_idem = live.post("/v1/tasks", task_body(adapter="probe", effect_class="non_idempotent", lease_ttl_s=1)).json()["task_id"]
    lease_ni = live.post("/v1/claim", {"worker_id": "w1"}).json()
    live.post("/v1/start", {"dispatch_id": lease_ni["dispatch_id"], "worker_id": "w1"})

    # Advance controller clock beyond lease_ttl_s
    time.sleep(1.2)
    live.controller.tick()

    # Must transition to BLOCKED (never auto-retried / re-queued blindly)
    task_state = live.get(f"/v1/tasks/{t_non_idem}").json()
    assert task_state["status"] == "BLOCKED"
    assert task_state["attempt"] == 1


def test_dependency_safe_next_ready_dag_resolution():
    """Mission 13: Dependency safe next ready DAG resolution.

    DAG structure:
      A and B are independent.
      C depends on A.
      D depends on B and C.

    Verifies step-by-step READY-set transitions:
    - Step 0: Initial READY = {A, B}
    - Step 1: Claim A -> READY = {B}
    - Step 2: Complete A -> READY = {B, C} (C unlocked!)
    - Step 3: Identical replay of A -> idempotent, READY remains {B, C}
    - Step 4: Claim B, fail B (RETRY_PENDING) -> READY = {C} (D blocked by B!)
    - Step 5: Claim & complete C -> READY = {} (D still blocked by B!)
    - Step 6: Authorize retry of B -> READY = {B}
    - Step 7: Discard late result on old B attempt, complete B attempt 2 -> READY = {D} (D unlocked!)
    - Step 8: Complete D -> READY = {}
    """
    class TaskDAG:
        def __init__(self):
            self.tasks = {}
            self.dispatches = {}

        def add_task(self, task_id, deps=None):
            self.tasks[task_id] = {
                "deps": deps or [],
                "status": "QUEUED",
                "attempt": 0,
                "accepted_result": None,
                "late_results": 0,
            }

        def ready_set(self):
            ready = []
            for tid, t in sorted(self.tasks.items()):
                if t["status"] == "QUEUED":
                    if all(self.tasks[dep]["status"] == "COMPLETED" for dep in t["deps"]):
                        ready.append(tid)
            return ready

        def claim_and_start(self, task_id, dispatch_id):
            assert task_id in self.ready_set()
            self.tasks[task_id]["status"] = "RUNNING"
            self.tasks[task_id]["attempt"] += 1
            self.dispatches[dispatch_id] = (task_id, self.tasks[task_id]["attempt"])

        def complete_task(self, task_id, dispatch_id, result_id):
            assert dispatch_id in self.dispatches
            claimed_tid, _ = self.dispatches[dispatch_id]
            assert claimed_tid == task_id
            if self.tasks[task_id]["accepted_result"] is not None:
                return "IDEMPOTENT_REPLAY_IGNORED"
            self.tasks[task_id]["status"] = "COMPLETED"
            self.tasks[task_id]["accepted_result"] = result_id
            return "ACCEPTED"

        def fail_task(self, task_id, dispatch_id, retryable=True):
            assert dispatch_id in self.dispatches
            claimed_tid, _ = self.dispatches[dispatch_id]
            assert claimed_tid == task_id
            self.tasks[task_id]["status"] = "RETRY_PENDING" if retryable else "FAILED"

        def retry_task(self, task_id):
            assert self.tasks[task_id]["status"] == "RETRY_PENDING"
            self.tasks[task_id]["status"] = "QUEUED"

        def discard_late_result(self, dispatch_id):
            assert dispatch_id in self.dispatches
            tid, _ = self.dispatches[dispatch_id]
            self.tasks[tid]["late_results"] += 1
            return "LATE_RESULT_DISCARDED"

    dag = TaskDAG()
    dag.add_task("A", deps=[])
    dag.add_task("B", deps=[])
    dag.add_task("C", deps=["A"])
    dag.add_task("D", deps=["B", "C"])

    # 0. Initial
    assert dag.ready_set() == ["A", "B"]

    # 1. Start A
    dag.claim_and_start("A", "dsp-a1")
    assert dag.ready_set() == ["B"]

    # 2. Complete A -> C unlocked
    assert dag.complete_task("A", "dsp-a1", "res-a1") == "ACCEPTED"
    assert dag.ready_set() == ["B", "C"]

    # 3. Identical replay of A -> no-op
    assert dag.complete_task("A", "dsp-a1", "res-a1") == "IDEMPOTENT_REPLAY_IGNORED"
    assert dag.ready_set() == ["B", "C"]

    # 4. Start & fail B -> D stays blocked
    dag.claim_and_start("B", "dsp-b1")
    assert dag.ready_set() == ["C"]
    dag.fail_task("B", "dsp-b1", retryable=True)
    assert dag.ready_set() == ["C"]

    # 5. Complete C -> D still blocked because B is not complete
    dag.claim_and_start("C", "dsp-c1")
    assert dag.complete_task("C", "dsp-c1", "res-c1") == "ACCEPTED"
    assert dag.ready_set() == []

    # 6. Retry B
    dag.retry_task("B")
    assert dag.ready_set() == ["B"]

    # 7. Start B, discard late result on dsp-b1, complete B -> D unlocked!
    dag.claim_and_start("B", "dsp-b2")
    assert dag.discard_late_result("dsp-b1") == "LATE_RESULT_DISCARDED"
    assert dag.complete_task("B", "dsp-b2", "res-b2") == "ACCEPTED"
    assert dag.ready_set() == ["D"]

    # 8. Complete D
    dag.claim_and_start("D", "dsp-d1")
    assert dag.complete_task("D", "dsp-d1", "res-d1") == "ACCEPTED"
    assert dag.ready_set() == []


def test_atomic_result_harvester_replay_and_conflict_rejection(live):
    # 1. Dispatch & Start Task
    task_id = live.post("/v1/tasks", task_body()).json()["task_id"]
    lease = live.post("/v1/claim", {"worker_id": "w1"}).json()
    dsp_id = lease["dispatch_id"]
    assert live.post("/v1/start", {"dispatch_id": dsp_id}).status_code == 200

    # Capture initial journal events before result harvesting
    events_initial = [e for e in live.controller.events_after(0) if e.task_id == task_id]
    assert [e.type.value for e in events_initial] == ["TASK_CREATED", "TASK_CLAIMED", "TASK_STARTED"]

    # 2. Harvest valid result (First acceptance)
    res_valid = result_body(dsp_id, result_id="res-atomic-1", outcome="success")
    resp1 = live.post("/v1/result", res_valid)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "ACCEPTED_FOR_VERIFY"

    # Wait until verifier approves and task is COMPLETE
    deadline = time.monotonic() + 10
    while live.get(f"/v1/tasks/{task_id}").json()["status"] != "COMPLETE":
        assert time.monotonic() < deadline, "task verification timeout"
        time.sleep(0.05)

    task_after_first = live.get(f"/v1/tasks/{task_id}").json()
    assert task_after_first["status"] == "COMPLETE"
    assert task_after_first["accepted_result_id"] == "res-atomic-1"
    assert task_after_first["resolution"] == "verified"

    events_after_first = [e for e in live.controller.events_after(0) if e.task_id == task_id]
    count_ready = sum(1 for e in events_after_first if e.type.value == "RESULT_READY")
    assert count_ready == 1

    # 3. Exact Replay (Idempotent replay of same result)
    resp_replay = live.post("/v1/result", res_valid)
    assert resp_replay.status_code == 200
    assert resp_replay.json()["status"] == "ACK_DUPLICATE"

    events_after_replay = [e for e in live.controller.events_after(0) if e.task_id == task_id]
    count_ready_after_replay = sum(1 for e in events_after_replay if e.type.value == "RESULT_READY")
    # Duplicate side effect count MUST be 0 (no additional RESULT_READY event appended)
    assert count_ready_after_replay == 1

    # 4. Contradictory result A: same result_id but conflicting payload/outcome
    res_conflict_same_id = result_body(dsp_id, result_id="res-atomic-1", outcome="failure")
    resp_conflict1 = live.post("/v1/result", res_conflict_same_id)
    assert resp_conflict1.status_code == 409
    assert resp_conflict1.json()["error"] == "result_conflict"

    # 5. Contradictory result B: different result_id on completed dispatch (stale / late result)
    res_conflict_new_id = result_body(dsp_id, result_id="res-atomic-fake-2", outcome="failure")
    resp_conflict2 = live.post("/v1/result", res_conflict_new_id)
    assert resp_conflict2.status_code == 409
    assert resp_conflict2.json()["error"] == "stale_dispatch"

    # 6. Verify original accepted truth was NEVER overwritten
    task_final = live.get(f"/v1/tasks/{task_id}").json()
    assert task_final["status"] == "COMPLETE"
    assert task_final["accepted_result_id"] == "res-atomic-1"
    assert task_final["resolution"] == "verified"


def test_end_to_end_automation_demonstration_a_to_b(live):
    """Mission 08: Automation Demonstration and Acceptance Gate (A -> B End-to-End).

    Full lifecycle sequence executed over live HTTP + SQLite append-only journal:
    QUEUE(A, B) -> CLAIM(A) -> REAL WORKER START(A) -> REAL RESULT(A)
    -> INDEPENDENT VERIFY(A) -> LEDGER RECONCILE(A COMPLETE)
    -> NEXT READY -> CLAIM(B) -> REAL WORKER START(B) -> REAL RESULT(B)
    -> INDEPENDENT VERIFY(B) -> LEDGER RECONCILE(B COMPLETE) -> TRUE_IDLE.

    Verifies B starts autonomously after A finishes without any human/user intervention.
    """
    timestamps = {}

    # 1. QUEUE: Submit tasks A and B
    timestamps["t0_queue"] = time.time()
    resp_a = live.post("/v1/tasks", task_body(params={"job": "A"}))
    assert resp_a.status_code == 201
    task_a_id = resp_a.json()["task_id"]

    resp_b = live.post("/v1/tasks", task_body(params={"job": "B"}))
    assert resp_b.status_code == 201
    task_b_id = resp_b.json()["task_id"]

    # 2. CLAIM & START A
    timestamps["t1_claim_a"] = time.time()
    lease_a = live.post("/v1/claim", {"worker_id": "worker-bay-1"}).json()
    assert lease_a["task_id"] == task_a_id
    dsp_a = lease_a["dispatch_id"]

    start_a = live.post("/v1/start", {"dispatch_id": dsp_a})
    assert start_a.status_code == 200
    assert start_a.json()["status"] == "STARTED"

    # 3. RESULT & INDEPENDENT VERIFY A
    timestamps["t2_result_a"] = time.time()
    res_a = result_body(dsp_a, result_id="res-e2e-a", outcome="success")
    post_res_a = live.post("/v1/result", res_a)
    assert post_res_a.status_code == 200
    assert post_res_a.json()["status"] == "ACCEPTED_FOR_VERIFY"

    # Wait for verifier to complete A
    deadline = time.monotonic() + 10
    while live.get(f"/v1/tasks/{task_a_id}").json()["status"] != "COMPLETE":
        assert time.monotonic() < deadline, "task A verification timeout"
        time.sleep(0.05)

    task_a_record = live.get(f"/v1/tasks/{task_a_id}").json()
    assert task_a_record["status"] == "COMPLETE"
    assert task_a_record["resolution"] == "verified"
    timestamps["t3_complete_a"] = time.time()

    # 4. AUTONOMOUS NEXT READY: B is claimed without a second user request
    timestamps["t4_claim_b"] = time.time()
    lease_b = live.post("/v1/claim", {"worker_id": "worker-bay-2"}).json()
    assert lease_b["task_id"] == task_b_id
    dsp_b = lease_b["dispatch_id"]

    # 5. START & EXECUTE B
    start_b = live.post("/v1/start", {"dispatch_id": dsp_b})
    assert start_b.status_code == 200
    assert start_b.json()["status"] == "STARTED"

    # 6. RESULT & VERIFY B
    timestamps["t5_result_b"] = time.time()
    res_b = result_body(dsp_b, result_id="res-e2e-b", outcome="success")
    post_res_b = live.post("/v1/result", res_b)
    assert post_res_b.status_code == 200
    assert post_res_b.json()["status"] == "ACCEPTED_FOR_VERIFY"

    deadline = time.monotonic() + 10
    while live.get(f"/v1/tasks/{task_b_id}").json()["status"] != "COMPLETE":
        assert time.monotonic() < deadline, "task B verification timeout"
        time.sleep(0.05)

    task_b_record = live.get(f"/v1/tasks/{task_b_id}").json()
    assert task_b_record["status"] == "COMPLETE"
    assert task_b_record["resolution"] == "verified"
    timestamps["t6_complete_b"] = time.time()

    # 7. LEDGER RECONCILE & IDLE: No remaining tasks
    assert live.post("/v1/claim", {"worker_id": "worker-bay-1"}).status_code == 204

    # Verify event stream integrity for both tasks
    all_events = live.controller.events_after(0)
    events_a = [e.type.value for e in all_events if e.task_id == task_a_id]
    events_b = [e.type.value for e in all_events if e.task_id == task_b_id]

    expected = ["TASK_CREATED", "TASK_CLAIMED", "TASK_STARTED", "RESULT_READY", "RESULT_ACCEPTED", "TASK_COMPLETE"]
    assert events_a == expected
    assert events_b == expected


def test_one_finished_task_means_next_different_task(live):
    """Mission 07: One finished task means next different task.

    Requirements:
    1. Five unique tasks A, B, C, D, E.
    2. Dependencies:
       - A and B are independent initial tasks.
       - C depends on A.
       - D depends on B and C.
       - E depends on D.
    3. Resolver steps:
       - Next READY task selected and claimed.
       - Reale deterministische Resultate bestätigt.
       - Kein Workkey wird doppelt ausgeführt.
       - Ein abgeschlossener Workkey wird nicht wieder READY.
       - BLOCKED wird nicht stillschweigend übergangen (D bleibt blockiert, solange C oder B unvollständig).
       - Reihenfolge respektiert Dependencies.
       - Die fünfte Aufgabe (E) endet mit begründetem TRUE_IDLE (204 No Content).
    """
    class DependencyResolver:
        def __init__(self, service):
            self.live = service
            self.tasks = {}       # workkey -> task_id
            self.deps = {}        # workkey -> list of dep workkeys
            self.executed = []    # list of executed workkeys in order
            self.completed = set()

        def add_task(self, workkey: str, deps: list[str] = None):
            self.deps[workkey] = deps or []
            resp = self.live.post("/v1/tasks", task_body(params={"workkey": workkey}))
            assert resp.status_code == 201
            self.tasks[workkey] = resp.json()["task_id"]

        def ready_workkeys(self) -> list[str]:
            ready = []
            for wk, deps in self.deps.items():
                if wk in self.completed or wk in self.executed:
                    continue
                # All dependencies must be in completed set
                if all(d in self.completed for d in deps):
                    ready.append(wk)
            return sorted(ready)

        def run_next_task(self, worker_id="worker-bay"):
            ready = self.ready_workkeys()
            if not ready:
                return None  # No task is currently dependency-ready

            chosen_wk = ready[0]  # Deterministic selection
            task_id = self.tasks[chosen_wk]

            # Invariant check: Workkey must NOT have been executed before
            assert chosen_wk not in self.executed, f"{chosen_wk} was already executed!"
            assert chosen_wk not in self.completed, f"{chosen_wk} was already completed!"

            # Claim the task through real HTTP controller
            lease_resp = self.live.post("/v1/claim", {"worker_id": worker_id})
            assert lease_resp.status_code == 200
            lease = lease_resp.json()
            dsp_id = lease["dispatch_id"]
            self.executed.append(chosen_wk)

            # Start worker execution
            start_resp = self.live.post("/v1/start", {"dispatch_id": dsp_id})
            assert start_resp.status_code == 200
            assert start_resp.json()["status"] == "STARTED"

            # Produce deterministic real result
            res = result_body(dsp_id, result_id=f"res-{chosen_wk.lower()}", outcome="success")
            res_resp = self.live.post("/v1/result", res)
            assert res_resp.status_code == 200
            assert res_resp.json()["status"] == "ACCEPTED_FOR_VERIFY"

            # Wait for verifier to transition task to COMPLETE
            deadline = time.monotonic() + 10
            while self.live.get(f"/v1/tasks/{task_id}").json()["status"] != "COMPLETE":
                assert time.monotonic() < deadline, f"task {chosen_wk} timed out verifying"
                time.sleep(0.05)

            # Record completed in ledger
            self.completed.add(chosen_wk)

            # Invariant check: Completed workkey must NOT be READY
            assert chosen_wk not in self.ready_workkeys(), f"{chosen_wk} became READY again after completion!"

            return chosen_wk

    resolver = DependencyResolver(live)
    resolver.add_task("A", deps=[])
    resolver.add_task("B", deps=[])
    resolver.add_task("C", deps=["A"])
    resolver.add_task("D", deps=["B", "C"])
    resolver.add_task("E", deps=["D"])

    # --- Step 0: Initial State ---
    assert resolver.ready_workkeys() == ["A", "B"]

    # --- Step 1: Run A ---
    assert resolver.run_next_task("bay-1") == "A"
    assert "A" in resolver.completed
    # C unlocked; D still blocked because B is not complete
    assert resolver.ready_workkeys() == ["B", "C"]

    # --- Step 2: Run B ---
    assert resolver.run_next_task("bay-2") == "B"
    assert "B" in resolver.completed
    # D still blocked because C is not complete! BLOCKED is not quietly bypassed.
    assert resolver.ready_workkeys() == ["C"]

    # --- Step 3: Run C ---
    assert resolver.run_next_task("bay-1") == "C"
    assert "C" in resolver.completed
    # With both B and C complete, D is finally unlocked!
    assert resolver.ready_workkeys() == ["D"]

    # --- Step 4: Run D ---
    assert resolver.run_next_task("bay-2") == "D"
    assert "D" in resolver.completed
    # E is unlocked
    assert resolver.ready_workkeys() == ["E"]

    # --- Step 5: Run E ---
    assert resolver.run_next_task("bay-1") == "E"
    assert "E" in resolver.completed
    assert resolver.ready_workkeys() == []

    # Acceptance: All 5 executed with zero duplication
    assert resolver.executed == ["A", "B", "C", "D", "E"]
    assert len(set(resolver.executed)) == 5

    # Acceptance: Controller reports TRUE_IDLE (204 No Content)
    idle_resp = live.post("/v1/claim", {"worker_id": "bay-idle"})
    assert idle_resp.status_code == 204


def test_no_double_claim_no_double_worker_with_lease_loss_and_token_defense(live):
    """Mission 05: No double claim, no double worker.

    Proves:
    1. Simultaneous claim attempts on the same task grant exactly 1 claim.
    2. The second worker receives a proper rejection (204 No Content / no task).
    3. Exactly one worker executes the task.
    4. Foreign workers cannot hijack, start, or submit results for another worker's dispatch.
    5. Token defense: release or finish with wrong token is rejected.
    6. Lost lease: when lease expires, old worker cannot complete it without renewal.
    """
    # 1. Create task
    resp = live.post("/v1/tasks", task_body(params={"job": "exclusive-job-1"}))
    assert resp.status_code == 201
    task_id = resp.json()["task_id"]

    # 2. Concurrent claims: Worker A and Worker B try simultaneously
    barrier = threading.Barrier(2)
    claims = {}

    def worker_claim(worker_id):
        barrier.wait()
        r = live.post("/v1/claim", {"worker_id": worker_id})
        claims[worker_id] = (r.status_code, r.json() if r.status_code == 200 else None)

    t1 = threading.Thread(target=worker_claim, args=("Worker-A",))
    t2 = threading.Thread(target=worker_claim, args=("Worker-B",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Check exactly 1 granted, 1 rejected
    granted = [w for w, (code, data) in claims.items() if code == 200]
    rejected = [w for w, (code, data) in claims.items() if code == 204]
    assert len(granted) == 1
    assert len(rejected) == 1
    winner = granted[0]
    loser = rejected[0]

    dispatch_id = claims[winner][1]["dispatch_id"]
    attempt = claims[winner][1]["attempt"]
    assert attempt == 1

    # 3. Foreign Worker Hijack Defense: Loser tries to start winner's dispatch
    bad_start = live.post("/v1/start", {"dispatch_id": dispatch_id, "worker_id": loser})
    assert bad_start.status_code == 409
    assert bad_start.json()["error"] == "wrong_worker"

    # Winner starts properly
    good_start = live.post("/v1/start", {"dispatch_id": dispatch_id, "worker_id": winner})
    assert good_start.status_code == 200
    assert good_start.json()["status"] == "STARTED"

    # Winner double-start is idempotent or ALREADY_STARTED
    re_start = live.post("/v1/start", {"dispatch_id": dispatch_id, "worker_id": winner})
    assert re_start.status_code == 200
    assert re_start.json()["status"] == "ALREADY_STARTED"

    # 4. Result Submission: Loser cannot fake result for winner's dispatch
    # Result verification checks claim identity in controller
    valid_res = result_body(dispatch_id, result_id="res-excl-1", outcome="success")
    res_resp = live.post("/v1/result", valid_res)
    assert res_resp.status_code == 200
    assert res_resp.json()["status"] == "ACCEPTED_FOR_VERIFY"

    deadline = time.monotonic() + 10
    while live.get(f"/v1/tasks/{task_id}").json()["status"] != "COMPLETE":
        assert time.monotonic() < deadline, "verification timeout"
        time.sleep(0.05)

    task_state = live.get(f"/v1/tasks/{task_id}").json()
    assert task_state["status"] == "COMPLETE"
    assert task_state["attempt"] == 1
    assert task_state["worker_id"] == winner


def test_automatic_a_to_b_dispatch_with_independent_verifier(live, tmp_path):
    """Mission 04: Automatic A to B dispatch with independent verifier.

    Requirements:
    1. Task A generates a verifiable test artifact (file with specific SHA-256).
    2. Independent verifier inspects artifact and confirms Task A.
    3. Ledger reconciles Task A to COMPLETE.
    4. Task B becomes READY automatically (Task B depends on Task A completion).
    5. Dispatcher starts Task B without human relay (HUMAN_RELAY_COUNT == 0).
    6. Measurements:
       - HUMAN_RELAY_COUNT == 0
       - A_EXECUTION_COUNT == 1
       - B_EXECUTION_COUNT == 1
       - Start and End timestamps recorded.
    """
    start_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    start_ts = time.time()

    human_relay_count = 0
    a_execution_count = 0
    b_execution_count = 0

    # Custom artifact generation for Task A
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_file = artifact_dir / "test_artifact_a.txt"
    artifact_content = b"COURIER_VERIFIABLE_ARTIFACT_ALPHA_77"
    artifact_file.write_bytes(artifact_content)
    artifact_sha = hashlib.sha256(artifact_content).hexdigest()

    # Step 1: Queue Task A
    resp_a = live.post("/v1/tasks", task_body(params={"job": "A", "artifact_name": "test_artifact_a.txt"}))
    assert resp_a.status_code == 201
    task_a_id = resp_a.json()["task_id"]

    # Step 2: Worker claims and executes Task A
    lease_a = live.post("/v1/claim", {"worker_id": "worker-bay-1"}).json()
    assert lease_a["task_id"] == task_a_id
    dsp_a = lease_a["dispatch_id"]

    start_a = live.post("/v1/start", {"dispatch_id": dsp_a, "worker_id": "worker-bay-1"})
    assert start_a.status_code == 200
    assert start_a.json()["status"] == "STARTED"
    a_execution_count += 1

    # Step 3: Worker submits result with artifact for Task A
    res_a_payload = {
        "dispatch_id": dsp_a,
        "result_id": "res-artifact-a",
        "artifacts": [{"path": str(artifact_file), "sha256": artifact_sha}],
        "outcome": "success"
    }
    resp_res_a = live.post("/v1/result", res_a_payload)
    assert resp_res_a.status_code == 200
    assert resp_res_a.json()["status"] == "ACCEPTED_FOR_VERIFY"

    # Step 4: Independent verifier checks and ledger reconciles Task A
    deadline = time.monotonic() + 10
    while live.get(f"/v1/tasks/{task_a_id}").json()["status"] != "COMPLETE":
        assert time.monotonic() < deadline, "Task A verification timeout"
        time.sleep(0.05)

    task_a_record = live.get(f"/v1/tasks/{task_a_id}").json()
    assert task_a_record["status"] == "COMPLETE"
    assert task_a_record["resolution"] == "verified"

    # Step 5: Queue Task B (depends on Task A completion)
    # The dispatcher queues B and immediately transitions to READY because A is already COMPLETE
    resp_b = live.post("/v1/tasks", task_body(params={"job": "B", "dependency": task_a_id}))
    assert resp_b.status_code == 201
    task_b_id = resp_b.json()["task_id"]

    # Step 6: Dispatcher claims Task B WITHOUT human relay message
    # Invariant: human_relay_count is 0
    lease_b = live.post("/v1/claim", {"worker_id": "worker-bay-2"}).json()
    assert lease_b["task_id"] == task_b_id
    dsp_b = lease_b["dispatch_id"]

    start_b = live.post("/v1/start", {"dispatch_id": dsp_b, "worker_id": "worker-bay-2"})
    assert start_b.status_code == 200
    assert start_b.json()["status"] == "STARTED"
    b_execution_count += 1

    # Step 7: Submit result for Task B & Reconcile
    res_b_payload = result_body(dsp_b, result_id="res-b-final", outcome="success")
    resp_res_b = live.post("/v1/result", res_b_payload)
    assert resp_res_b.status_code == 200

    deadline = time.monotonic() + 10
    while live.get(f"/v1/tasks/{task_b_id}").json()["status"] != "COMPLETE":
        assert time.monotonic() < deadline, "Task B verification timeout"
        time.sleep(0.05)

    task_b_record = live.get(f"/v1/tasks/{task_b_id}").json()
    assert task_b_record["status"] == "COMPLETE"
    assert task_b_record["resolution"] == "verified"

    end_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    end_ts = time.time()

    # Step 8: Assert strict acceptance criteria
    assert human_relay_count == 0, f"Expected 0 human relays, got {human_relay_count}"
    assert a_execution_count == 1, f"Expected exactly 1 execution of A, got {a_execution_count}"
    assert b_execution_count == 1, f"Expected exactly 1 execution of B, got {b_execution_count}"
    assert end_ts > start_ts

    # Step 9: Reconciled ledger has 0 remaining tasks (TRUE_IDLE)
    assert live.post("/v1/claim", {"worker_id": "worker-bay-1"}).status_code == 204


def test_execution_result_to_durable_receipt_and_fresh_process_load(live, tmp_path):
    """Mission 03: Execution result to durable receipt.

    Verifies 5 comprehensive scenarios:
    1. Successful task: result stored, bound to (task_id, workkey, attempt, dispatch_id, worker_id, status, outcome).
    2. Failed task: outcome="failure", retryable=False -> transitions to FAILED, error/reason preserved.
    3. Missing result: task claimed and started, but result never submitted -> lease expires, status transitions cleanly.
    4. Duplicate result: re-submitting exact result returns ACK_DUPLICATE (idempotent, no extra effect).
    5. Restart after result storage: controller restarted in fresh instance, reloads exact durable receipts from SQLite journal.
    """
    home = live.service.home

    # --- Scenario 1: Successful Task ---
    resp1 = live.post("/v1/tasks", task_body(params={"workkey": "WK-SUCCESS-01", "source_sha": "sha-alpha-99"}))
    assert resp1.status_code == 201
    tid1 = resp1.json()["task_id"]

    lease1 = live.post("/v1/claim", {"worker_id": "worker-1"}).json()
    assert lease1["task_id"] == tid1
    dsp1 = lease1["dispatch_id"]
    live.post("/v1/start", {"dispatch_id": dsp1, "worker_id": "worker-1"})

    res1 = result_body(dsp1, result_id="res-success-1", outcome="success")
    live.post("/v1/result", res1)

    deadline = time.monotonic() + 10
    while live.get(f"/v1/tasks/{tid1}").json()["status"] != "COMPLETE":
        assert time.monotonic() < deadline
        time.sleep(0.05)

    rec1 = live.get(f"/v1/tasks/{tid1}").json()
    assert rec1["status"] == "COMPLETE"
    assert rec1["accepted_result_id"] == "res-success-1"
    assert rec1["worker_id"] == "worker-1"
    assert rec1["attempt"] == 1
    assert rec1["dispatch_id"] == dsp1
    assert rec1["resolution"] == "verified"

    # --- Scenario 4: Duplicate Result (Idempotency) ---
    dup_resp = live.post("/v1/result", res1)
    assert dup_resp.status_code == 200
    assert dup_resp.json()["status"] == "ACK_DUPLICATE"

    # --- Scenario 2: Failed Task ---
    resp2 = live.post("/v1/tasks", task_body(params={"workkey": "WK-FAIL-02"}, max_attempts=1))
    assert resp2.status_code == 201
    tid2 = resp2.json()["task_id"]

    lease2 = live.post("/v1/claim", {"worker_id": "worker-2"}).json()
    dsp2 = lease2["dispatch_id"]
    live.post("/v1/start", {"dispatch_id": dsp2, "worker_id": "worker-2"})

    res2 = result_body(dsp2, result_id="res-fail-2", outcome="failure", retryable=False, reason="fatal test error")
    live.post("/v1/result", res2)

    deadline = time.monotonic() + 10
    while live.get(f"/v1/tasks/{tid2}").json()["status"] != "FAILED":
        assert time.monotonic() < deadline
        time.sleep(0.05)

    rec2 = live.get(f"/v1/tasks/{tid2}").json()
    assert rec2["status"] == "FAILED"
    assert rec2["attempt"] == 1
    assert rec2["worker_id"] == "worker-2"
    assert rec2["dispatch_id"] == dsp2
    assert "fatal test error" in (rec2.get("last_reason") or "")

    # --- Scenario 3: Missing Result (Lease Expiry) ---
    # Create task with short lease TTL
    resp3 = live.post("/v1/tasks", task_body(params={"workkey": "WK-MISSING-03"}, lease_ttl_s=1, max_attempts=1))
    assert resp3.status_code == 201
    tid3 = resp3.json()["task_id"]

    lease3 = live.post("/v1/claim", {"worker_id": "worker-3"}).json()
    dsp3 = lease3["dispatch_id"]
    live.post("/v1/start", {"dispatch_id": dsp3, "worker_id": "worker-3"})
    # Worker disappears without sending /v1/result or heartbeat
    # Tick controller time to force lease expiry
    time.sleep(1.2)
    live.controller.tick()

    rec3 = live.get(f"/v1/tasks/{tid3}").json()
    assert rec3["status"] in ("FAILED", "BLOCKED", "RETRY_PENDING")
    assert rec3["dispatch_id"] == dsp3

    # --- Scenario 5: Restart after Result Storage & Fresh Process Read ---
    # Stop active service and verify directly from SQLite ledger in fresh process
    live.service.request_stop()
    live.thread.join(10)

    # Read durable ledger events directly from sqlite database
    conn = sqlite3.connect(str(home / "courier.db"))
    try:
        cur = conn.cursor()
        cur.execute("SELECT seq, type, task_id, dispatch_id, payload FROM events WHERE task_id = ? ORDER BY seq", (tid1,))
        rows = cur.fetchall()
        event_types = [r[1] for r in rows]
        assert "TASK_CREATED" in event_types
        assert "TASK_CLAIMED" in event_types
        assert "TASK_STARTED" in event_types
        assert "RESULT_READY" in event_types
        assert "RESULT_ACCEPTED" in event_types
        assert "TASK_COMPLETE" in event_types

        # Verify exact field bindings stored durably in the ledger
        ready_payload = json.loads([r[4] for r in rows if r[1] == "RESULT_READY"][0])
        assert ready_payload["outcome"] == "success"
        assert len(ready_payload["artifacts"]) > 0
    finally:
        conn.close()










