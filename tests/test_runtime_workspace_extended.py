import os
import sys
import pytest

from courier_runtime.workspace import Step, Workspace
from courier_runtime.hosts import Host, Requirement
from courier_runtime.grants import Broker, Request
from courier_runtime.continuation import AcceptedLog
from courier_runtime.ownership import Registry
from courier_runtime.lease import LeaseStore


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def workspace_env(tmp_path):
    clock = Clock()
    hosts = [Host("dev-1", frozenset({"python"}), privacy="own")]
    broker = Broker(clock)
    leases = LeaseStore(str(tmp_path / "lease.db"), clock=clock)
    log = AcceptedLog(str(tmp_path / "accepted.jsonl"))
    reg = Registry(str(tmp_path / "owned.json"))
    ws = Workspace(
        hosts=hosts,
        lease_store=leases,
        broker=broker,
        accepted_log=log,
        registry=reg,
        workdir=str(tmp_path),
        clock=clock,
    )
    req = Request("r1", "p1", "fs.write", frozenset({"workspace:p1"}), "any", "", "project", "write", "idempotent")
    yield ws, broker, req, tmp_path
    leases.close()


def test_workspace_step_fails_when_command_exits_nonzero(workspace_env):
    ws, broker, req, tmp = workspace_env
    broker.authorize(req)
    broker.grant(req, "g1", expires_at=None)

    step = Step("failing_step", [sys.executable, "-c", "import sys; sys.exit(42)"], "never_created.txt")
    result = ws.run("wk-fail", Requirement(frozenset({"python"}), privacy="own"), "scope-1", req, [step])

    assert result["state"] == "FAILED"
    assert result["step"] == 0
    assert "exit 42" in result["reasons"][0]
    assert len(ws.evidence) == 1
    assert ws.evidence[0].passed is False


def test_workspace_step_fails_when_output_missing(workspace_env):
    ws, broker, req, tmp = workspace_env
    broker.authorize(req)
    broker.grant(req, "g1", expires_at=None)

    # Exits 0 but does not create expected output file
    step = Step("silent_step", [sys.executable, "-c", "pass"], "missing_output.txt")
    result = ws.run("wk-missing", Requirement(frozenset({"python"}), privacy="own"), "scope-2", req, [step])

    assert result["state"] == "FAILED"
    assert len(ws.evidence) == 1
    assert ws.evidence[0].passed is False
    assert ws.log.facts("wk-missing") == []


def test_workspace_needs_user_when_grant_missing(workspace_env):
    ws, broker, req, tmp = workspace_env
    # Broker not granted authority
    step = Step("ok_step", [sys.executable, "-c", "pass"], "ok.txt")
    result = ws.run("wk-unauth", Requirement(frozenset({"python"}), privacy="own"), "scope-3", req, [step])

    assert result["state"] == "NEEDS_USER"
    assert any("authority required" in r for r in result["reasons"])
