import os
import sys
from dataclasses import FrozenInstanceError

import pytest

from courier_runtime.continuation import AcceptedLog
from courier_runtime.grants import Broker, Request
from courier_runtime.hosts import Host, Requirement
from courier_runtime.lease import LeaseStore
from courier_runtime.ownership import Registry
from courier_runtime.workspace import Step, Workspace


class MockClock:
    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t


@pytest.fixture
def workspace_env(tmp_path):
    clock = MockClock()
    hosts = [
        Host("local-mac", frozenset({"python", "macos"}), cost_per_hour_eur=0.0, privacy="own"),
    ]
    broker = Broker(clock)
    req = Request("req-1", "proj-1", "fs.write", frozenset({"workspace:proj-1"}), "any", "", "project", "write", "idempotent")
    broker.authorize(req)
    broker.grant(req, "grant-1", expires_at=None)

    leases = LeaseStore(str(tmp_path / "lease.db"), clock=clock)
    accepted_log = AcceptedLog(str(tmp_path / "accepted.jsonl"))
    registry = Registry(str(tmp_path / "owned.json"))

    ws = Workspace(
        hosts=hosts,
        lease_store=leases,
        broker=broker,
        accepted_log=accepted_log,
        registry=registry,
        workdir=str(tmp_path),
        clock=clock,
        lease_ttl_s=30,
    )
    yield ws, clock, req, tmp_path
    leases.close()


def test_step_immutability():
    step = Step("test_step", [sys.executable, "-c", "pass"], "out.txt")
    assert step.effect_class == "idempotent"
    with pytest.raises(FrozenInstanceError):
        step.output = "new_out.txt"


def test_workspace_step_failure_nonzero_exit(workspace_env):
    ws, _, req, tmp = workspace_env
    # Step exits with code 42
    failing_step = Step("fail_nonzero", [sys.executable, "-c", "import sys; sys.exit(42)"], "never.txt")
    result = ws.run("wk-fail-1", Requirement(frozenset({"python"})), "workspace:proj-1", req, [failing_step])

    assert result["state"] == "FAILED"
    assert result["step"] == 0
    assert "exit 42" in result["reasons"][0]
    # No orphaned owned process left behind
    assert ws.registry.owned("wk-fail-1") == []


def test_workspace_step_failure_missing_output(workspace_env):
    ws, _, req, tmp = workspace_env
    # Step exits 0 but does not create declared output file
    missing_out_step = Step("no_file", [sys.executable, "-c", "pass"], "missing.txt")
    result = ws.run("wk-fail-2", Requirement(frozenset({"python"})), "workspace:proj-1", req, [missing_out_step])

    assert result["state"] == "FAILED"
    assert result["step"] == 0
    assert ws.registry.owned("wk-fail-2") == []


def test_workspace_unauthorized_request_needs_user(workspace_env):
    ws, _, _, tmp = workspace_env
    # Request for an unauthorized scope without a grant
    unauth_req = Request("req-unauth", "proj-1", "net.send", frozenset({"net:unrestricted"}), "any", "", "project", "write", "idempotent")
    step = Step("dummy", [sys.executable, "-c", "pass"], "out.txt")
    result = ws.run("wk-unauth", Requirement(frozenset({"python"})), "workspace:proj-1", unauth_req, [step])

    assert result["state"] == "NEEDS_USER"
    assert "authority required" in result["reasons"][0]
