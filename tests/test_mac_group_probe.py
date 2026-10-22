"""A failed process-group probe must not report the group as gone."""

import os
import subprocess

from scripts.mac_worker.runtime_state import group_exists


def test_permission_probe_failure_does_not_call_the_group_dead(monkeypatch):
    def killpg(pgid, sig):
        raise PermissionError("EPERM")

    def check_output(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ps", timeout=1)

    monkeypatch.setattr(os, "killpg", killpg)
    monkeypatch.setattr(subprocess, "check_output", check_output)
    assert group_exists(4242) is True
