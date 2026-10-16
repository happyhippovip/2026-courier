"""Gate 4 (Restart & Recovery) – open interruption scenarios from plan §9
(Windows GUI freeze, docs/WINDOWS_GUI_FREEZE_INCIDENT_2026-10-02.md).

Invariant: a broken surface never means lost work, and a resume never
silently doubles an effect. Tests marked xfail(strict=True) were shown red
against integration/v1 and document a real gap; strict=True turns them into
a CI failure the moment the gap is fixed so the marker must be removed.
"""
import json
import os
import subprocess
import sys
import time

import pytest

from courier_runtime.continuation import AcceptedLog
from courier_runtime.hosts import Requirement
from courier_runtime.kirby import KirbySupervisor
from courier_runtime.lease import LeaseStore
from courier_runtime.ownership import Registry
from courier_runtime.workspace import Step, Workspace
from test_runtime_own_computer import request, world, write_step  # noqa: F401  (fixture)


def _wait_for(path, timeout=20):
    deadline = time.monotonic() + timeout
    while not os.path.exists(path):
        assert time.monotonic() < deadline, f"{path} never appeared"
        time.sleep(0.05)


def _fresh_workspace(ws, tmp, clock):
    """Same durable files, new process state: what a forced reboot leaves behind."""
    return Workspace(hosts=ws.hosts, lease_store=ws.leases, broker=ws.broker,
                     accepted_log=AcceptedLog(str(tmp / "accepted.jsonl")),
                     registry=Registry(str(tmp / "owned.json")), workdir=str(tmp), clock=clock, lease_ttl_s=30)


@pytest.mark.xfail(strict=True, reason=(
    "G4 terminal host dies, worker keeps running: Workspace.run only accepts a step when it waited "
    "for the process itself. A step that finished successfully after its host/terminal died is not "
    "adopted (its output + exit are never evidenced), so the resume re-executes it -> silent double effect."))
def test_terminal_host_dies_but_finished_worker_step_is_adopted_not_rerun(world):
    ws, clock, _, tmp = world
    runs = tmp / "runs.txt"
    steps = [write_step(n, str(runs)) for n in ("fetch", "transform", "report")]
    lost = ws.run("wk-term", Requirement(frozenset({"python"})), "project:p1", request("r1"), steps, stop_after=1)
    assert lost["state"] == "DEVICE_LOST"
    _wait_for(str(tmp / "transform.out"))          # the worker finished on its own
    time.sleep(0.3)
    clock.t += 60                                   # the dead host's lease expired
    done = ws.run("wk-term", Requirement(frozenset({"python"})), "project:p1", request("r2"), steps)
    assert done["state"] == "DONE"
    assert runs.read_text().splitlines() == ["fetch", "transform", "report"]


@pytest.mark.xfail(strict=True, reason=(
    "G4 forced restart after checkpoint: Checkpoint.from_log never fills `attempted`, so a "
    "non-idempotent step that was started before the reboot is invisible to decide(); the resume "
    "re-runs it blindly instead of returning NEEDS_USER (V1_RULE_0: uncertain outcome -> BLOCKED)."))
def test_forced_restart_after_checkpoint_blocks_uncertain_non_idempotent_step(world):
    ws, clock, _, tmp = world
    runs = tmp / "runs.txt"
    first = write_step("send", str(runs))
    steps = [Step(first.name, first.argv, first.output, effect_class="non_idempotent"),
             write_step("report", str(runs))]
    lost = ws.run("wk-boot", Requirement(frozenset({"python"})), "project:p1", request("r1"), steps, stop_after=0)
    assert lost["state"] == "DEVICE_LOST"
    _wait_for(str(tmp / "send.out"))               # effect may have happened, nobody accepted it
    time.sleep(0.3)
    clock.t += 60
    rebooted = _fresh_workspace(ws, tmp, clock)
    after = rebooted.run("wk-boot", Requirement(frozenset({"python"})), "project:p1", request("r2"), steps)
    assert after["state"] == "NEEDS_USER", after
    assert runs.read_text().splitlines() == ["send"]


@pytest.mark.xfail(strict=True, reason=(
    "G4 restart with verified continuation: Workspace resumes from AcceptedLog.last step without "
    "re-checking that the accepted evidence (sha256 in the fact sources) still matches the artifact "
    "on disk; a lost/changed accepted artifact is silently built upon."))
def test_verified_continuation_rechecks_accepted_evidence_before_resume(world):
    ws, clock, _, tmp = world
    runs = tmp / "runs.txt"
    steps = [write_step(n, str(runs)) for n in ("fetch", "transform", "report")]
    lost = ws.run("wk-verify", Requirement(frozenset({"python"})), "project:p1", request("r1"), steps, stop_after=1)
    assert lost["state"] == "DEVICE_LOST"
    ws.registry.stop("wk-verify")
    (tmp / "fetch.out").write_text("tampered after acceptance")
    clock.t += 60
    rebooted = _fresh_workspace(ws, tmp, clock)
    after = rebooted.run("wk-verify", Requirement(frozenset({"python"})), "project:p1", request("r2"), steps)
    assert after["state"] != "DONE", "continued on top of evidence that no longer verifies"
    assert after["state"] in ("NEEDS_USER", "RECOVERING", "FAILED"), after


@pytest.mark.xfail(strict=True, reason=(
    "G4 IDE crash with uncommitted work: Kirby's CriticalSnapshot records only `git rev-parse HEAD` "
    "(of the process CWD); dirty/untracked files are not captured, so the recovery evidence cannot "
    "show that uncommitted work existed or where it is."))
def test_ide_crash_snapshot_records_uncommitted_work(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo)]
    subprocess.run(git + ["init", "-q"], check=True)
    (repo / "done.py").write_text("x = 1\n")
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-qm", "base"], check=True)
    (repo / "done.py").write_text("x = 2  # unsaved-to-git edit\n")
    (repo / "wip_feature.py").write_text("print('wip')\n")
    monkeypatch.chdir(repo)
    kirby = KirbySupervisor("muse", "win-1", "sess-ide", str(tmp_path))
    kirby._take_snapshot({"workkey": "wk-ide", "state": "RUNNING"})
    text = (tmp_path / "snapshot_sess-ide.json").read_text()
    snap = json.loads(text)
    assert snap["current_sha"]                     # HEAD itself is captured today
    assert "wip_feature.py" in text and "done.py" in text, snap
