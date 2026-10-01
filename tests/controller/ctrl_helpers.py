"""Helpers for the L2 controller suite (tests/controller)."""

import hashlib
import threading
from pathlib import Path

import requests

from courier_core.controller import Controller
from courier_core.serve import Service
from courier_core.verification import Verdict

SHA = hashlib.sha256(b"courier-golden").hexdigest()


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class Verifiers:
    """Injectable verifier registry: adapter name -> verify function."""

    def __init__(self, **verify_fns):
        self.verify_fns = verify_fns
        self.calls = []

    def __call__(self, adapter):
        fn = self.verify_fns.get(adapter)
        if fn is None:
            return None

        def wrapped(task, result, home):
            self.calls.append((task.task_id, result.result_id))
            return fn(task, result, home)
        return wrapped


def accept_all(task, result, home):
    return Verdict(True, "ok")


def sha_matches(task, result, home):
    ok = any(a.get("sha256") == SHA for a in result.payload["artifacts"])
    return Verdict(ok, "sha matches" if ok else "sha mismatch", retryable=False)


def task_body(**overrides):
    body = {"adapter": "probe", "params": {"x": 1}, "effect_class": "idempotent", "max_attempts": 3,
            "lease_ttl_s": 6}
    body.update(overrides)
    return body


def result_body(dispatch_id, result_id="r1", outcome="success", sha=SHA, **extra):
    body = {"dispatch_id": dispatch_id, "result_id": result_id,
            "artifacts": [{"path": "out.txt", "sha256": sha}], "outcome": outcome}
    body.update(extra)
    return body


def make_controller(home, clock=None, verifier=None, **kw):
    return Controller(Path(home), clock=clock or FakeClock(), verifier=verifier or Verifiers(probe=accept_all),
                      **kw).boot()


def run_attempt(ctl, worker="w1", outcome="success", result_id="r1"):
    """Claim -> start -> result for the next queued task; returns the lease."""
    lease = ctl.claim({"worker_id": worker})
    ctl.start({"dispatch_id": lease["dispatch_id"]})
    ctl.result(result_body(lease["dispatch_id"], result_id=result_id, outcome=outcome))
    return lease


def types(ctl, task_id):
    return [e.type.value for e in ctl.journal.events(task_id=task_id) if e.type.value != "TASK_PROGRESS"]


class LiveService:
    """The real HTTP service in-process (port 0), stoppable like the process."""

    def __init__(self, home, verifier=None, clock=None):
        controller = Controller(Path(home), verifier=verifier or Verifiers(probe=accept_all),
                                **({"clock": clock} if clock else {}))
        self.service = Service(Path(home), 0, controller=controller)
        self.controller = self.service.controller
        self.thread = threading.Thread(target=self.service.run, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.service.port}"
        self.session = requests.Session()
        self.session.headers["X-Courier-Token"] = self.service.token

    def get(self, path, **kw):
        kw.setdefault("timeout", 10)
        return self.session.get(self.base + path, **kw)

    def post(self, path, body=None, **kw):
        kw.setdefault("timeout", 10)
        return self.session.post(self.base + path, json=body, **kw)

    def stop(self):
        self.service.request_stop()
        self.thread.join(15)
        assert not self.thread.is_alive(), "service did not stop"
