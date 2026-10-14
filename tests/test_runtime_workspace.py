"""Targeted unit tests for courier_runtime.workspace.

Covers Step dataclass, Workspace initialization, host selection,
authorization gating, continuation decision gates, step execution,
output and exit-code validation, evidence generation, checkpoint resumption,
device loss simulation, and lease fencing.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import subprocess
import sys
import pytest

from courier_runtime.continuation import AcceptedFact, AcceptedLog
from courier_runtime.grants import Broker, Request
from courier_runtime.hosts import Host, NoEligibleHost, Requirement
from courier_runtime.lease import LeaseStore, StaleLease
from courier_runtime.ownership import OwnedProcess, Registry
from courier_runtime.workspace import Step, Workspace, _alive, _sha256


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, delta: float) -> None:
        self.t += delta


@pytest.fixture
def workspace_env(tmp_path):
    clock = FakeClock()
    hosts = [
        Host("host-cloud", frozenset({"python", "linux"}), cost_per_hour_eur=0.10, privacy="hosted"),
        Host("host-local", frozenset({"python", "macos"}), cost_per_hour_eur=0.0, privacy="own"),
    ]
    broker = Broker(clock)
    req = Request("req-1", "user-1", "fs.write", frozenset({"workspace:p1"}), "any", "", "project", "write", "idempotent")
    broker.authorize(req)
    broker.grant(req, "grant-1", expires_at=None)

    lease_db = str(tmp_path / "lease.db")
    leases = LeaseStore(lease_db, clock=clock)
    log = AcceptedLog(str(tmp_path / "accepted.jsonl"))
    registry = Registry(str(tmp_path / "owned.json"))

    ws = Workspace(
        hosts=hosts,
        lease_store=leases,
        broker=broker,
        accepted_log=log,
        registry=registry,
        workdir=str(tmp_path),
        clock=clock,
        lease_ttl_s=30,
    )
    yield ws, clock, req, tmp_path
    leases.close()


def test_step_dataclass_properties():
    step = Step(name="compile", argv=["echo", "1"], output="bin.out", effect_class="transactional")
    assert step.name == "compile"
    assert step.argv == ["echo", "1"]
    assert step.output == "bin.out"
    assert step.effect_class == "transactional"

    # Default effect_class
    default_step = Step(name="test", argv=["echo"], output="test.out")
    assert default_step.effect_class == "idempotent"

    # Immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        step.name = "mutate"  # type: ignore[misc]


def test_step_equality_and_unhashable():
    s1 = Step("run", ["python", "app.py"], "app.out")
    s2 = Step("run", ["python", "app.py"], "app.out")
    s3 = Step("run", ["python", "other.py"], "app.out")

    assert s1 == s2
    assert s1 != s3
    # dataclass with list field cannot be hashed
    with pytest.raises(TypeError, match="unhashable type: 'list'"):
        hash(s1)


def test_sha256_helper(tmp_path):
    sample = tmp_path / "sample.bin"
    content = b"courier payload 2026"
    sample.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert _sha256(str(sample)) == expected


def test_alive_helper(tmp_path):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        record = OwnedProcess.capture(proc.pid, "wk-alive", "host-local")
        assert _alive(record) is True
    finally:
        proc.kill()
        proc.wait()

    assert _alive(record) is False


def test_workspace_initialization(tmp_path):
    clock = FakeClock()
    leases = LeaseStore(str(tmp_path / "lease_init.db"), clock=clock)
    log = AcceptedLog(str(tmp_path / "accepted_init.jsonl"))
    registry = Registry(str(tmp_path / "owned_init.json"))
    broker = Broker(clock)

    ws = Workspace(
        hosts=[],
        lease_store=leases,
        broker=broker,
        accepted_log=log,
        registry=registry,
        workdir=str(tmp_path),
        clock=clock,
        lease_ttl_s=45,
    )
    assert ws.ttl == 45
    assert ws.evidence == []
    assert ws.workdir == str(tmp_path)
    leases.close()


def test_run_empty_steps(workspace_env):
    ws, _, req, _ = workspace_env
    res = ws.run("wk-empty", Requirement(frozenset({"python"})), "scope:empty", req, [])
    assert res["state"] == "DONE"
    assert res["steps"] == 0
    assert res["host"] in ("host-cloud", "host-local")
    # Lease must be released
    assert ws.leases.current("scope:empty") is None


def test_run_explicit_host(workspace_env):
    ws, _, req, _ = workspace_env
    cloud_host = next(h for h in ws.hosts if h.device_id == "host-cloud")
    res = ws.run("wk-explicit", Requirement(frozenset({"python"})), "scope:cloud", req, [], host=cloud_host)
    assert res["host"] == "host-cloud"


def test_run_no_eligible_host_raises(workspace_env):
    ws, _, req, _ = workspace_env
    with pytest.raises(NoEligibleHost):
        ws.run("wk-none", Requirement(frozenset({"quantum_accelerator"})), "scope:quantum", req, [])


def test_run_unauthorized_request(workspace_env):
    ws, _, _, tmp_path = workspace_env
    unauth_req = Request("req-unauth", "user-1", "fs.read", frozenset({"outside"}), "any", "", "project", "read", "idempotent")
    step = Step("write", [sys.executable, "-c", "open('bad.txt', 'w').write('x')"], "bad.txt")

    res = ws.run("wk-unauth", Requirement(frozenset({"python"})), "scope:unauth", unauth_req, [step])
    assert res["state"] == "NEEDS_USER"
    assert any("authority required" in r for r in res["reasons"])
    assert not (tmp_path / "bad.txt").exists()
    assert ws.leases.current("scope:unauth") is None


def test_run_unsafe_active_lease_blocks(workspace_env):
    ws, _, req, tmp_path = workspace_env
    # Another device acquires the lease
    ws.leases.acquire("scope:busy", "foreign-device", "wk-other", ttl_s=60)
    step = Step("write", [sys.executable, "-c", "open('busy.txt', 'w').write('x')"], "busy.txt")

    local_host = next(h for h in ws.hosts if h.device_id == "host-local")
    res = ws.run("wk-busy", Requirement(frozenset({"python"})), "scope:busy", req, [step], host=local_host)
    assert res["state"] == "WAITING"
    assert not (tmp_path / "busy.txt").exists()


def test_run_lease_held_by_same_host_is_reacquired(workspace_env):
    ws, _, req, tmp_path = workspace_env
    local_host = next(h for h in ws.hosts if h.device_id == "host-local")
    # Same host already holds the lease
    ws.leases.acquire("scope:same", local_host.device_id, "wk-same", ttl_s=60)

    step = Step("write", [sys.executable, "-c", "open('same.txt', 'w').write('1')"], "same.txt")
    res = ws.run("wk-same", Requirement(frozenset({"python"})), "scope:same", req, [step], host=local_host)
    assert res["state"] == "DONE"
    assert (tmp_path / "same.txt").read_text() == "1"


def test_run_unsafe_living_process_triggers_recovering(workspace_env):
    ws, _, req, tmp_path = workspace_env
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        ws.registry.add(OwnedProcess.capture(proc.pid, "wk-owned", "host-local"))
        step = Step("write", [sys.executable, "-c", "open('owned.txt', 'w').write('x')"], "owned.txt")
        res = ws.run("wk-owned", Requirement(frozenset({"python"})), "scope:owned", req, [step])
        assert res["state"] == "RECOVERING"
        assert not (tmp_path / "owned.txt").exists()
    finally:
        proc.kill()
        proc.wait()
        ws.registry.stop("wk-owned")


def test_run_step_nonzero_exit_fails(workspace_env):
    ws, _, req, tmp_path = workspace_env
    step = Step("fail_step", [sys.executable, "-c", "import sys; sys.exit(7)"], "fail.out")
    res = ws.run("wk-fail", Requirement(frozenset({"python"})), "scope:fail", req, [step])

    assert res["state"] == "FAILED"
    assert res["step"] == 0
    assert "exit 7" in res["reasons"][0]
    assert len(ws.evidence) == 1
    assert ws.evidence[0].passed is False
    assert ws.evidence[0].artifact_sha256 == ""
    assert ws.log.facts("wk-fail") == []
    assert ws.registry.owned("wk-fail") == []


def test_run_step_missing_output_file_fails(workspace_env):
    ws, _, req, tmp_path = workspace_env
    # Exits 0 but does not create missing.out
    step = Step("no_out", [sys.executable, "-c", "pass"], "missing.out")
    res = ws.run("wk-no-out", Requirement(frozenset({"python"})), "scope:no-out", req, [step])

    assert res["state"] == "FAILED"
    assert res["step"] == 0
    assert "exit 0" in res["reasons"][0]
    assert len(ws.evidence) == 1
    assert ws.evidence[0].passed is False
    assert ws.evidence[0].artifact_sha256 == ""
    assert ws.log.facts("wk-no-out") == []


def test_run_failure_on_intermediate_step(workspace_env):
    ws, _, req, tmp_path = workspace_env
    step0 = Step("s0", [sys.executable, "-c", "open('s0.out', 'w').write('ok')"], "s0.out")
    step1 = Step("s1", [sys.executable, "-c", "import sys; sys.exit(2)"], "s1.out")
    step2 = Step("s2", [sys.executable, "-c", "open('s2.out', 'w').write('ok')"], "s2.out")

    res = ws.run("wk-inter", Requirement(frozenset({"python"})), "scope:inter", req, [step0, step1, step2])
    assert res["state"] == "FAILED"
    assert res["step"] == 1
    assert "exit 2" in res["reasons"][0]

    # Step 0 succeeded and was logged
    facts = ws.log.facts("wk-inter")
    assert len(facts) == 1
    assert facts[0].step == 0

    # Step 2 never ran
    assert not (tmp_path / "s2.out").exists()
    assert len(ws.evidence) == 2
    assert ws.evidence[0].passed is True
    assert ws.evidence[1].passed is False


def test_run_stop_after_simulates_device_loss(workspace_env):
    ws, _, req, tmp_path = workspace_env
    step0 = Step("s0", [sys.executable, "-c", "import time; time.sleep(5)"], "s0.out")
    res = ws.run("wk-lost", Requirement(frozenset({"python"})), "scope:lost", req, [step0], stop_after=0)

    try:
        assert res["state"] == "DEVICE_LOST"
        assert res["step"] == 0
        assert "pid" in res
        # Process should be registered and still alive
        alive = ws.registry.owned("wk-lost")
        assert len(alive) == 1
        assert alive[0].pid == res["pid"]
        # Lease is still held (not released because device was abruptly lost)
        assert ws.leases.current("scope:lost") is not None
    finally:
        # Clean up spawned background process
        ws.registry.stop("wk-lost")


def test_run_resumes_from_last_accepted_step(workspace_env):
    ws, clock, req, tmp_path = workspace_env
    out0 = tmp_path / "step0.out"
    out1 = tmp_path / "step1.out"

    # Pre-populate step 0 in accepted log
    out0.write_text("done 0")
    h0 = hashlib.sha256(out0.read_bytes()).hexdigest()
    ws.log.append(AcceptedFact("wk-resume", 0, "s0 produced step0.out", (f"evidence:{h0}",), "controller", clock()))

    code1 = "import pathlib; pathlib.Path('step1.out').write_text('done 1')"
    step0 = Step("s0", [sys.executable, "-c", "raise RuntimeError('should not run')"], "step0.out")
    step1 = Step("s1", [sys.executable, "-c", code1], "step1.out")

    res = ws.run("wk-resume", Requirement(frozenset({"python"})), "scope:resume", req, [step0, step1])
    assert res["state"] == "DONE"
    assert res["steps"] == 2
    assert out1.read_text() == "done 1"
    facts = ws.log.facts("wk-resume")
    assert [f.step for f in facts] == [0, 1]


def test_run_sequential_multi_step_success(workspace_env):
    ws, _, req, tmp_path = workspace_env
    steps = [
        Step(f"step_{i}", [sys.executable, "-c", f"open('out_{i}.txt', 'w').write('{i}')"], f"out_{i}.txt")
        for i in range(3)
    ]

    res = ws.run("wk-multi", Requirement(frozenset({"python"})), "scope:multi", req, steps)
    assert res["state"] == "DONE"
    assert res["steps"] == 3
    assert len(ws.evidence) == 3
    assert all(e.passed for e in ws.evidence)

    facts = ws.log.facts("wk-multi")
    assert [f.step for f in facts] == [0, 1, 2]
    for i in range(3):
        assert (tmp_path / f"out_{i}.txt").read_text() == str(i)
        assert facts[i].sources[0] == f"evidence:{ws.evidence[i].artifact_sha256}"

    # Lease is released and registry is clear
    assert ws.leases.current("scope:multi") is None
    assert ws.registry.owned("wk-multi") == []


def test_run_fenced_lease_theft_raises_stale_lease(workspace_env):
    ws, clock, req, tmp_path = workspace_env

    original_renew = ws.leases.renew

    def tampering_renew(lease, ttl_s=30):
        renewed = original_renew(lease, ttl_s=ttl_s)
        # Advance time beyond expiry and let an attacker take over the lease
        clock.advance(100)
        ws.leases.acquire("scope:stolen", "attacker-host", "wk-stolen", ttl_s=300)
        return renewed

    ws.leases.renew = tampering_renew

    step = Step("s", [sys.executable, "-c", "open('tamper.out', 'w').write('1')"], "tamper.out")
    with pytest.raises(StaleLease):
        ws.run("wk-tamper", Requirement(frozenset({"python"})), "scope:stolen", req, [step])
