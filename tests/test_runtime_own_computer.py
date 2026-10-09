"""Vertical slice: Courier keeps working on its own host, survives a device loss,
and never widens authority or accepts evidence from the wrong host."""
import sys

import pytest

from courier_runtime.continuation import AcceptedLog, Checkpoint, decide
from courier_runtime.grants import Broker, Request
from courier_runtime.hosts import (DEGRADED, Evidence, Host, NoEligibleHost, Requirement, accept_evidence,
                                   select)
from courier_runtime.lease import LeaseStore
from courier_runtime.ownership import Registry
from courier_runtime.receipt import RecoveryReceipt, validate
from courier_runtime.workspace import Step, Workspace


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def write_step(name, count_file):
    code = (f"import pathlib; p = pathlib.Path({count_file!r}); "
            f"p.write_text(p.read_text() + {name!r} + '\\n' if p.exists() else {name!r} + '\\n'); "
            f"pathlib.Path({name + '.out'!r}).write_text('ok')")
    return Step(name, [sys.executable, "-c", code], name + ".out")


@pytest.fixture
def world(tmp_path):
    clock = Clock()
    hosts = [Host("cloud-1", frozenset({"python", "linux"}), cost_per_hour_eur=0.05, privacy="hosted"),
             Host("mac-1", frozenset({"python", "macos"}), privacy="own"),
             Host("win-1", frozenset({"python", "windows_native"}), privacy="own")]
    broker = Broker(clock)
    req = Request("r0", "p1", "fs.write", frozenset({"workspace:p1"}), "any", "", "project", "write", "idempotent")
    broker.authorize(req)
    broker.grant(req, "g1", expires_at=None)
    leases = LeaseStore(str(tmp_path / "lease.db"), clock=clock)
    ws = Workspace(hosts=hosts, lease_store=leases, broker=broker, accepted_log=AcceptedLog(str(tmp_path / "accepted.jsonl")),
                   registry=Registry(str(tmp_path / "owned.json")), workdir=str(tmp_path), clock=clock, lease_ttl_s=30)
    yield ws, clock, req, tmp_path
    leases.close()


def request(rid):
    return Request(rid, "p1", "fs.write", frozenset({"workspace:p1"}), "any", "", "project", "write", "idempotent")


def test_intent_to_done_on_a_selected_host(world):
    ws, _, _, tmp = world
    steps = [write_step(n, str(tmp / "runs.txt")) for n in ("fetch", "transform", "report")]
    result = ws.run("wk-1", Requirement(frozenset({"python"}), privacy="own"), "project:p1", request("r1"), steps)
    assert result["state"] == "DONE" and result["host"] == "mac-1"     # own device preferred by requirement
    assert [f.step for f in ws.log.facts("wk-1")] == [0, 1, 2]
    assert all(f.sources[0].startswith("evidence:") and f.accepted_by == "controller" for f in ws.log.facts())
    assert ws.registry.owned("wk-1") == []                             # nothing of ours left running


def test_device_loss_resumes_on_another_host_from_last_accepted_step(world):
    ws, clock, _, tmp = world
    runs = tmp / "runs.txt"
    steps = [write_step(n, str(runs)) for n in ("fetch", "transform", "report")]
    lost = ws.run("wk-2", Requirement(frozenset({"python"})), "project:p1", request("r1"), steps, stop_after=1)
    assert lost["state"] == "DEVICE_LOST" and lost["host"] == "mac-1"     # cheapest eligible host

    # Recovery: the dead device's owned tree is retired by identity, never by name.
    survivors = ws.registry.owned("wk-2")
    owned = {(r.pid, r.create_time) for r in survivors}
    stop = ws.registry.stop("wk-2")
    receipt = validate(RecoveryReceipt(
        workkey="wk-2", session_id="mac-1", incident_fingerprint="device_lost", detected_state="DEVICE_LOST",
        detected_at=clock(), what_failed="worker_process", positive_evidence="heartbeat lease expired",
        survived={"last_accepted_step": 0}, action="RETIRE_OWNED_TREE", outcome="WAITING",
        retired=[{"pid": r.pid, "create_time": r.create_time} for r in survivors],
        resume_from={"step": 1}), owned)
    assert receipt.outcome == "WAITING" and stop[0]["workkey"] == "wk-2"

    clock.t += 31                                                       # lease of the lost device expires
    win = next(h for h in ws.hosts if h.device_id == "win-1")
    done = ws.run("wk-2", Requirement(frozenset({"python"})), "project:p1", request("r2"), steps, host=win)
    assert done["state"] == "DONE" and done["host"] == "win-1"
    assert [f.step for f in ws.log.facts("wk-2")] == [0, 1, 2]
    assert runs.read_text().splitlines().count("fetch") == 1            # accepted step 0 was not re-run


def test_lost_device_still_holding_the_lease_blocks_takeover(world):
    ws, _, _, tmp = world
    steps = [write_step(n, str(tmp / "r.txt")) for n in ("a", "b")]
    ws.run("wk-3", Requirement(frozenset({"python"})), "project:p1", request("r1"), steps, stop_after=0)
    ws.registry.stop("wk-3")
    win = next(h for h in ws.hosts if h.device_id == "win-1")
    result = ws.run("wk-3", Requirement(frozenset({"python"})), "project:p1", request("r2"), steps, host=win)
    assert result["state"] == "WAITING"                                  # no second writer while the lease lives


def test_no_grant_means_needs_user_not_execution(world):
    ws, _, _, tmp = world
    wider = Request("r9", "p1", "fs.write", frozenset({"workspace:p1", "home:~"}), "any", "", "project", "write",
                    "idempotent")
    result = ws.run("wk-4", Requirement(frozenset({"python"})), "project:p1", wider, [write_step("x", str(tmp / "r"))])
    assert result["state"] == "NEEDS_USER" and not (tmp / "x.out").exists()


def test_windows_requirement_never_runs_or_evidences_on_linux(world):
    ws, _, _, _ = world
    assert select(Requirement(frozenset({"windows_native"})), ws.hosts).device_id == "win-1"
    degraded = [h if h.device_id != "win-1" else Host("win-1", h.capabilities, health=DEGRADED) for h in ws.hosts]
    with pytest.raises(NoEligibleHost):
        select(Requirement(frozenset({"windows_native"})), degraded)
    linux_ev = Evidence("wk", "windows_native", "cloud-1", "abc", True)
    assert accept_evidence(linux_ev, "windows_native", ws.hosts)[0] is False
    assert accept_evidence(Evidence("wk", "windows_native", "win-1", "abc", True), "windows_native", ws.hosts)[0]


def test_continuation_refuses_unsafe_resumes():
    cp = Checkpoint("wk", ["a", "b", "c"], last_accepted_step=0,
                    attempted={1: {"effect_class": "non_idempotent", "effect_confirmed": False}}, grant_ids=["g1"])
    assert decide(cp, grants_valid={"g1": True}, owned_alive=[], lease_available=True)["state"] == "NEEDS_USER"
    cp.attempted = {}
    assert decide(cp, grants_valid={"g1": False}, owned_alive=[], lease_available=True)["state"] == "NEEDS_USER"
    assert decide(cp, grants_valid={"g1": True}, owned_alive=[123], lease_available=True)["state"] == "RECOVERING"
    assert decide(cp, grants_valid={"g1": True}, owned_alive=[], lease_available=False)["state"] == "WAITING"
    ok = decide(cp, grants_valid={"g1": True}, owned_alive=[], lease_available=True)
    assert ok["safe"] and ok["resume_step"] == 1


def test_accepted_log_rejects_unsourced_or_unauthorized_facts(tmp_path):
    from courier_runtime.continuation import AcceptedFact
    log = AcceptedLog(str(tmp_path / "a.jsonl"))
    with pytest.raises(ValueError):
        log.append(AcceptedFact("wk", 0, "x", (), "controller", 1.0))
    with pytest.raises(ValueError):
        log.append(AcceptedFact("wk", 0, "x", ("ev",), "model", 1.0))


def test_workspace_rejects_step_effect_escalation(world):
    ws, _, _, tmp = world
    escalated_step = Step("dangerous", [sys.executable, "-c", "import sys; sys.exit(0)"], "d.out", effect_class="non_idempotent")
    result = ws.run("wk-sec-1", Requirement(frozenset({"python"})), "project:p1", request("r1"), [escalated_step])
    assert result["state"] == "NEEDS_USER"
    assert "not covered by request effect" in result["reasons"][0]
    assert ws.leases.current("project:p1") is None  # lease cleanly released


def test_workspace_rejects_path_traversal_escaping_workdir(world):
    ws, _, _, tmp = world
    escape_step = Step("escape", [sys.executable, "-c", "import sys; sys.exit(0)"], "../escaped.out")
    result = ws.run("wk-sec-2", Requirement(frozenset({"python"})), "project:p1", request("r1"), [escape_step])
    assert result["state"] == "FAILED"
    assert "output path escapes workdir" in result["reasons"][0]
    assert ws.leases.current("project:p1") is None  # lease cleanly released


def test_workspace_halts_when_grant_expires_mid_execution(world):
    ws, clock, _, tmp = world
    # Step 0 passes, but grant is revoked before step 1
    steps = [write_step("s0", str(tmp / "cnt.txt")), write_step("s1", str(tmp / "cnt.txt"))]
    # Revoke grant after step 0 starts by wrapping broker authorize
    original_authorize = ws.broker.authorize
    call_count = [0]
    def exp_authorize(req):
        call_count[0] += 1
        if call_count[0] > 2:  # After initial run check and step 0
            return (None, "EXPIRED", "grant expired")
        return original_authorize(req)
    ws.broker.authorize = exp_authorize

    result = ws.run("wk-sec-3", Requirement(frozenset({"python"})), "project:p1", request("r1"), steps)
    assert result["state"] == "NEEDS_USER"
    assert "authority expired during execution" in result["reasons"][0]
    assert ws.leases.current("project:p1") is None

