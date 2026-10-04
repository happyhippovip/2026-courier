"""The controller half of the golden contract, driven by the real golden harness.

tests/golden/golden_harness.Courier starts `python -m courier_core.serve`, reads
the token, talks to /v1, reads the journal read-only, follows SSE and does the
offline verify + rebuild on a copy - exactly as the golden tests will. L3 (the
worker host) and L4 (adapters.synthetic) do not exist yet, so a scripted HTTP
"worker" plays L3 and a probe adapter plays L4's verifier. Everything the
controller is responsible for in each golden scenario is asserted here; the
process-tree parts stay with the real golden tests.
"""

import json
import os
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden"
sys.path.insert(0, str(GOLDEN_DIR))
from golden_harness import GOLDEN_SHA256, Courier, synthetic_params  # noqa: E402

GOLDEN_SEQUENCE = ["TASK_CREATED", "TASK_CLAIMED", "TASK_STARTED", "RESULT_READY", "RESULT_ACCEPTED",
                   "TASK_COMPLETE"]

PROBE_ADAPTER = textwrap.dedent('''
    """Test-only stand-in for an L4 adapter verifier."""
    import hashlib
    from courier_core.verification import Verdict

    def verify(task, result, home):
        expected = hashlib.sha256(task.params.get("content", "courier-golden").encode()).hexdigest()
        ok = any(a.get("sha256") == expected for a in result.payload["artifacts"])
        return Verdict(ok, "artifact hash matches" if ok else "artifact hash mismatch", retryable=False)
''')


class ControllerOnly(Courier):
    """The golden Courier with a probe adapter package first on PYTHONPATH."""

    def __init__(self, home, logs, probe_dir):
        super().__init__(home, logs)
        self.probe_dir = probe_dir

    def env(self):
        env = super().env()
        env["PYTHONPATH"] = os.pathsep.join([str(self.probe_dir), env["PYTHONPATH"]])
        return env

    def _spawn(self, args, log_name, new_group=False):
        # `python -m` puts the cwd first on sys.path. Run from the probe dir so the
        # probe `adapters` package wins over the repo's real one (lane L4).
        log = open(self.logs / log_name, "ab")
        self._log_handles.append(log)
        proc = subprocess.Popen([sys.executable, "-m", *args], cwd=str(self.probe_dir), env=self.env(),
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        self.tracked_pids.add(proc.pid)
        return proc

    def make_probe_task(self, **kw):
        body = {"adapter": "l2probe", "params": synthetic_params(), "effect_class": kw.pop("effect_class", "idempotent"),
                "max_attempts": kw.pop("max_attempts", 3), "lease_ttl_s": kw.pop("lease_ttl_s", 6)}
        response = self.api.post("/v1/tasks", body)
        assert response.status_code in (200, 201), response.text
        return response.json()["task_id"]


class FakeWorker:
    """Plays L3 over HTTP: claim, start, heartbeat, result."""

    def __init__(self, courier, worker_id="golden-worker"):
        self.courier, self.worker_id = courier, worker_id

    def claim(self):
        response = self.courier.api.post("/v1/claim", {"worker_id": self.worker_id})
        assert response.status_code == 200, response.text
        return response.json()

    def start(self, lease):
        assert self.courier.api.post("/v1/start", {"dispatch_id": lease["dispatch_id"]}).status_code == 200

    def beat(self, *leases):
        return self.courier.api.post("/v1/heartbeat", {"worker_id": self.worker_id,
                                                       "dispatch_ids": [l["dispatch_id"] for l in leases]})

    def result(self, lease, result_id=None, sha=GOLDEN_SHA256, outcome="success", **extra):
        body = {"dispatch_id": lease["dispatch_id"], "result_id": result_id or f"res-{lease['dispatch_id']}",
                "artifacts": [{"path": "out.txt", "sha256": sha}], "outcome": outcome, **extra}
        return self.courier.api.post("/v1/result", body)


@pytest.fixture
def courier(tmp_path):
    probe = tmp_path / "probe"
    (probe / "adapters").mkdir(parents=True)
    (probe / "adapters" / "__init__.py").touch()
    (probe / "adapters" / "l2probe.py").write_text(PROBE_ADAPTER)
    home, logs = tmp_path / "courier_home", tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    instance = ControllerOnly(home, logs, probe)
    yield instance
    instance.close()


def payload(event):
    return json.loads(event["payload"] or "{}")


def test_golden_happy_path_controller_half(courier, tmp_path):
    courier.start_controller()
    worker = FakeWorker(courier)
    task_id = courier.make_probe_task()
    lease = worker.claim()
    worker.start(lease)
    assert worker.result(lease).json()["status"] == "ACCEPTED_FOR_VERIFY"
    courier.wait_event(task_id, "TASK_COMPLETE", timeout=20)

    events = courier.task_events(task_id)
    assert courier.task_types(task_id) == GOLDEN_SEQUENCE
    assert len({e["dispatch_id"] for e in events if e["dispatch_id"]}) == 1
    assert {e["attempt"] for e in events if e["attempt"] is not None} == {1}
    ready = next(e for e in events if e["type"] == "RESULT_READY")
    assert any(a["sha256"] == GOLDEN_SHA256 for a in payload(ready)["artifacts"])

    all_seqs = [e["seq"] for e in courier.all_events()]
    assert courier.read_sse_seqs(until_seq=all_seqs[-1]) == all_seqs

    live_hash = courier.projection_hash()
    controller_pid = courier.controller.pid
    courier.stop_controller_graceful()
    from golden_harness import pids_alive
    assert pids_alive([controller_pid]) == []

    report, copy_hash, rebuilt_hash = courier.verify_and_rebuild(tmp_path)
    assert report.ok and copy_hash == live_hash and rebuilt_hash == live_hash

    courier.start_controller()
    assert courier.api.get("/v1/health").json()["mode"] == "normal"
    assert courier.projection_hash() == live_hash
    assert courier.task_types(task_id) == GOLDEN_SEQUENCE


def test_duplicate_result_controller_half(courier):
    courier.start_controller()
    worker = FakeWorker(courier)
    task_id = courier.make_probe_task()
    lease = worker.claim()
    worker.start(lease)
    worker.result(lease, result_id="r-1")
    courier.wait_event(task_id, "TASK_COMPLETE", timeout=20)
    ready = next(e for e in courier.task_events(task_id) if e["type"] == "RESULT_READY")
    before = len(courier.all_events())
    response = courier.api.post("/v1/result", {"dispatch_id": ready["dispatch_id"], "result_id": ready["result_id"],
                                               "artifacts": payload(ready)["artifacts"], "outcome": "success"})
    assert response.status_code == 200 and response.json()["status"] == "ACK_DUPLICATE"
    assert len(courier.all_events()) == before


def test_late_result_controller_half(courier):
    courier.start_controller()
    task_id = courier.make_probe_task(lease_ttl_s=3)
    stale = courier.api.post("/v1/claim", {"worker_id": "golden-fake-worker"}).json()
    assert courier.api.post("/v1/start", {"dispatch_id": stale["dispatch_id"]}).status_code == 200
    courier.wait_event(task_id, "LEASE_EXPIRED", timeout=20)
    worker = FakeWorker(courier)
    lease = worker.claim()
    worker.start(lease)
    worker.result(lease)
    complete = courier.wait_event(task_id, "TASK_COMPLETE", timeout=20)
    assert complete["attempt"] == 2
    late = courier.api.post("/v1/result", {"dispatch_id": stale["dispatch_id"], "result_id": "late-result-attempt-1",
                                           "artifacts": [{"path": "out.txt", "sha256": GOLDEN_SHA256}],
                                           "outcome": "success"})
    assert late.status_code == 409
    courier.wait_event(task_id, "LATE_RESULT_DISCARDED", timeout=10)
    accepted = [e for e in courier.task_events(task_id) if e["type"] == "RESULT_ACCEPTED"]
    assert len(accepted) == 1 and accepted[0]["attempt"] == 2 and accepted[0]["result_id"] != "late-result-attempt-1"


def test_transient_failures_controller_half(courier):
    courier.start_controller()
    worker = FakeWorker(courier)
    task_id = courier.make_probe_task(max_attempts=3)
    for n in (1, 2):
        lease = worker.claim()
        worker.start(lease)
        worker.result(lease, outcome="failure", retryable=True, reason="transient provider error")
        courier.wait_event(task_id, "TASK_RETRY_SCHEDULED", timeout=20, count=n)
    lease = worker.claim()
    worker.start(lease)
    worker.result(lease)
    complete = courier.wait_event(task_id, "TASK_COMPLETE", timeout=20)
    assert complete["attempt"] == 3
    assert [e["type"] for e in courier.task_events(task_id)].count("RESULT_REJECTED") == 2


def test_non_idempotent_worker_loss_blocks(courier):
    courier.start_controller()
    task_id = courier.make_probe_task(effect_class="non_idempotent", lease_ttl_s=3)
    worker = FakeWorker(courier)
    worker.start(worker.claim())  # the worker then "dies": no more heartbeats
    courier.wait_event(task_id, "LEASE_EXPIRED", timeout=20)
    courier.wait_event(task_id, "TASK_BLOCKED", timeout=20)
    time.sleep(4)
    assert courier.api.post("/v1/claim", {"worker_id": "other"}).status_code == 204
    assert [e["type"] for e in courier.task_events(task_id)].count("TASK_CLAIMED") == 1


def test_cancel_while_running_controller_half(courier):
    courier.start_controller()
    task_id = courier.make_probe_task()
    worker = FakeWorker(courier)
    lease = worker.claim()
    worker.start(lease)
    assert courier.api.post(f"/v1/tasks/{task_id}/cancel").status_code == 200
    courier.wait_event(task_id, "TASK_CANCEL_REQUESTED", timeout=10)
    assert worker.beat(lease).json()["cancel"] == [lease["dispatch_id"]]
    worker.beat()  # tree killed and reaped: the dispatch is no longer reported
    courier.wait_event(task_id, "TASK_CANCELLED", timeout=10)
    assert worker.result(lease).status_code == 409
    assert not [e for e in courier.task_events(task_id) if e["type"] in ("RESULT_ACCEPTED", "TASK_COMPLETE")]


def test_controller_restart_mid_run_keeps_the_dispatch(courier):
    courier.start_controller()
    task_id = courier.make_probe_task(lease_ttl_s=12)
    worker = FakeWorker(courier)
    lease = worker.claim()
    worker.start(lease)
    courier.kill_controller()
    courier.start_controller()
    for _ in range(4):  # the worker keeps beating every 2 s through the restart
        assert worker.beat(lease).json()["stop"] == []
        time.sleep(2)
    worker.result(lease)
    courier.wait_event(task_id, "TASK_COMPLETE", timeout=20)
    events = courier.task_events(task_id)
    assert "LEASE_EXPIRED" not in [e["type"] for e in events]
    assert len({e["dispatch_id"] for e in events if e["dispatch_id"]}) == 1


def test_restart_grace_expires_vanished_worker(courier):
    courier.start_controller()
    task_id = courier.make_probe_task(lease_ttl_s=3)
    worker = FakeWorker(courier)
    worker.start(worker.claim())
    courier.kill_controller()  # worker also gone: no heartbeats at all
    courier.start_controller()
    expired = courier.wait_event(task_id, "LEASE_EXPIRED", timeout=20)
    assert payload(expired)["reason"] == "restart_grace"


def test_corrupt_journal_starts_degraded_and_read_only(courier):
    """The golden corruption recipe, verbatim."""
    courier.start_controller()
    worker = FakeWorker(courier)
    task_id = courier.make_probe_task()
    lease = worker.claim()
    worker.start(lease)
    worker.result(lease)
    courier.wait_event(task_id, "TASK_COMPLETE", timeout=20)
    courier.stop_controller_graceful()

    conn = sqlite3.connect(str(courier.db_path))
    try:
        for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'events'").fetchall():
            conn.execute(f'DROP TRIGGER "{name}"')
        seq, body = conn.execute("SELECT seq, payload FROM events ORDER BY seq LIMIT 1 OFFSET 1").fetchone()
        tampered = json.loads(body or "{}")
        tampered["golden_tampered"] = True
        conn.execute("UPDATE events SET payload = ? WHERE seq = ?", (json.dumps(tampered), seq))
        conn.commit()
    finally:
        conn.close()

    courier.start_controller()
    health = courier.api.get("/v1/health").json()
    assert health["mode"] == "degraded_readonly", health
    assert isinstance(health.get("first_bad_seq"), int) and health["first_bad_seq"] <= seq, health
    refused = courier.api.post("/v1/tasks", {
        "adapter": "synthetic", "params": {}, "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 6})
    assert refused.status_code == 503, refused.text
