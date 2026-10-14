"""Worker continuity recovery (48h acceptance, section D).

Proves the Courier worker parks honestly and resumes across the
interruptions an unattended run must survive. Each test drives a real file
home and a real local HTTP stub controller on 127.0.0.1; nothing here
touches the live journal or the network beyond loopback.

STATUS: WRITTEN, NOT YET EXECUTED (authoring window has no shell).
Run:  python -m pytest -q tests/test_worker_continuity_recovery.py
A failure is a real continuity defect for the L3 owner, not a bad test:
every assertion below pins behavior the product already promises
(outbox redelivery, idle-on-unreachable, fail-closed token handling,
claim-execute-deliver-next progression).

Covers (mission section D):
  D1  process death between run and delivery -> identical-bytes redelivery
  D2  controller flap (down, then up) -> park idle, then resume delivery
  D3  missing controller token -> idle (fail closed), never a crash
  D4  two queued tasks -> delivered in order (NEXT WORKKEY progression)

Deliberately NOT pinned here: WorkerLoop.run() exits(4) when the
controller is unhealthy at startup, and the logon task carries no
restart policy. That boot-order combination is a routed supervision
finding (see handoffs/continuity_unit_20261008.json), not behavior
this suite endorses.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from courier_worker import service as S

TOKEN = "continuity-token"
EFFECT_KEY = "cfx-" + "b" * 40


class FlapState:
    """Minimal stub controller: claim queue, result sink, down switch."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.claims = []
        self.results = []
        self.down = False
        self.result_down = False


FLAP = FlapState()


class FlapHandler(BaseHTTPRequestHandler):
    server_version = "Flap/1"

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

    def _guard(self):
        if FLAP.down or (FLAP.result_down and self.path == "/v1/result"):
            try:
                self.connection.shutdown(2)
            except OSError:
                pass
            self.connection.close()
            return False
        if self.headers.get("X-Courier-Token") != TOKEN:
            self._json(401)
            return False
        return True

    def do_GET(self):
        if self.path == "/v1/health":
            if FLAP.down:
                self.connection.close()
                return
            self._json(200, {"mode": "normal", "head_seq": 0})
        else:
            self._json(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode()) if raw else {}
        except ValueError:
            payload = {}
        if not self._guard():
            return
        if self.path == "/v1/claim":
            if FLAP.claims:
                self._json(200, FLAP.claims.pop(0))
            else:
                self._json(204)
        elif self.path == "/v1/start":
            self._json(200, {})
        elif self.path == "/v1/heartbeat":
            self._json(200, {})
        elif self.path == "/v1/result":
            FLAP.results.append(payload)
            self._json(200, {"status": "ACCEPTED_FOR_VERIFY"})
        else:
            self._json(404)


@pytest.fixture()
def flap():
    FLAP.reset()
    server = ThreadingHTTPServer(("127.0.0.1", 0), FlapHandler)
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


def claim_body(dispatch="d1", task="t1", content="courier-continuity"):
    return {
        "task_id": task,
        "attempt": 1,
        "dispatch_id": dispatch,
        "ttl_s": 30,
        "spec": {
            "adapter": "synthetic",
            "effect_class": "idempotent",
            "timeout_s": 30,
            "effect_key": EFFECT_KEY,
            "params": {"sleep_s": 0, "write": "out.txt", "content": content},
        },
    }


def outbox_files(home):
    box = home / "outbox"
    if not box.is_dir():
        return []
    return sorted(p for p in box.glob("*.json") if p.is_file())


def test_process_death_redelivers_identical_bytes(tmp_path, flap):
    """D1: a result parked in the outbox is redelivered byte-identical."""
    write_token(tmp_path)
    FLAP.claims.append(claim_body())
    FLAP.result_down = True  # run succeeds locally; delivery cannot reach us
    loop1 = S.WorkerLoop(str(tmp_path), flap, "w1", 0.2)
    assert loop1.iterate(threading.Event()) == "delivered"
    assert FLAP.results == []  # nothing acknowledged
    parked = outbox_files(tmp_path)
    assert len(parked) == 1  # the result survived the "process death"
    first_bytes = parked[0].read_bytes()

    # Fresh process, same home: must redeliver the identical payload once.
    FLAP.result_down = False
    loop2 = S.WorkerLoop(str(tmp_path), flap, "w1", 0.2)
    assert loop2.iterate(threading.Event()) == "idle"  # flush only, no claim
    assert outbox_files(tmp_path) == []
    assert len(FLAP.results) == 1
    assert json.loads(first_bytes)["result_id"] == FLAP.results[0]["result_id"]
    assert FLAP.results[0]["dispatch_id"] == "d1"
    assert FLAP.results[0]["outcome"] == "success"
    digest = hashlib.sha256(b"courier-continuity").hexdigest()
    assert FLAP.results[0]["artifacts"] == [{"path": "artifacts/d1/out.txt", "sha256": digest}]

    # A third pass must not duplicate anything.
    loop3 = S.WorkerLoop(str(tmp_path), flap, "w1", 0.2)
    assert loop3.iterate(threading.Event()) == "idle"
    assert len(FLAP.results) == 1


def test_controller_flap_parks_then_resumes(tmp_path, flap):
    """D2: unreachable controller -> idle park; recovery -> delivery."""
    write_token(tmp_path)
    dead = S.WorkerLoop(str(tmp_path), "http://127.0.0.1:9", "w1", 0.2)
    assert dead.iterate(threading.Event()) == "idle"  # refused: park, no crash
    assert outbox_files(tmp_path) == []

    FLAP.claims.append(claim_body())
    live = S.WorkerLoop(str(tmp_path), flap, "w1", 0.2)
    assert live.iterate(threading.Event()) == "delivered"
    assert [r["dispatch_id"] for r in FLAP.results] == ["d1"]
    assert outbox_files(tmp_path) == []


def test_missing_token_parks_idle_then_recovers(tmp_path, flap):
    """D3: no token file -> fail-closed idle; token appears -> delivery."""
    FLAP.claims.append(claim_body())
    loop = S.WorkerLoop(str(tmp_path), flap, "w1", 0.2)
    assert loop.iterate(threading.Event()) == "idle"  # no token: park, no crash
    assert FLAP.results == []

    write_token(tmp_path)
    loop2 = S.WorkerLoop(str(tmp_path), flap, "w1", 0.2)
    assert loop2.iterate(threading.Event()) == "delivered"
    assert [r["dispatch_id"] for r in FLAP.results] == ["d1"]


def test_two_queued_tasks_deliver_in_order(tmp_path, flap):
    """D4: CLAIM -> EXECUTE -> DELIVER -> NEXT WORKKEY progression."""
    write_token(tmp_path)
    FLAP.claims.append(claim_body(dispatch="d1", task="t1", content="first"))
    FLAP.claims.append(claim_body(dispatch="d2", task="t2", content="second"))
    loop = S.WorkerLoop(str(tmp_path), flap, "w1", 0.2)
    assert loop.iterate(threading.Event()) == "delivered"
    assert loop.iterate(threading.Event()) == "delivered"
    assert [r["dispatch_id"] for r in FLAP.results] == ["d1", "d2"]
    assert all(r["outcome"] == "success" for r in FLAP.results)
    assert outbox_files(tmp_path) == []
    assert loop.iterate(threading.Event()) == "idle"
