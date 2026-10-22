"""A failed process-group probe must not report the group as gone."""

import os
import subprocess

from scripts.mac_worker.muse_supervisor import ProcessLauncher
from scripts.mac_worker.runtime_state import group_exists
import scripts.mac_worker.muse_supervisor as supervisor
import scripts.mac_worker.runtime_state as state


def test_permission_probe_failure_does_not_call_the_group_dead(monkeypatch):
    def killpg(pgid, sig):
        raise PermissionError("EPERM")

    def check_output(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ps", timeout=1)

    monkeypatch.setattr(os, "killpg", killpg)
    monkeypatch.setattr(subprocess, "check_output", check_output)
    assert group_exists(4242) is True


def test_bool_pid_is_not_process_one(monkeypatch):
    """True is not pid 1. A bool must not be probed or signaled."""
    calls = []

    def fake_ps(cmd, **kwargs):
        calls.append(list(cmd))
        return "1 1 Thu Oct 22 00:00:00 2026 /sbin/init"

    killed = []
    monkeypatch.setattr(state.subprocess, "check_output", fake_ps)
    monkeypatch.setattr(state.os, "killpg", lambda pgid, sig: killed.append(("killpg", pgid, sig)))
    monkeypatch.setattr(supervisor.os, "kill", lambda pid, sig: killed.append(("kill", pid, sig)))
    identity = state.process_identity(True)
    group = state.group_exists(True)
    group_false = state.group_exists(False)
    alive = ProcessLauncher().is_alive("01", True)
    assert (identity, calls, group, group_false, alive, killed) == (None, [], False, False, False, [])
