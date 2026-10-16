"""Gate G1: a Windows job kill is fail-closed, and testable without Windows.

The real kernel32 path is skipped on this host. The contract is the
terminate_job_tree abstraction: the job is what dies, a failed
TerminateJobObject does not become a successful reap, and a process that
is still alive afterwards blocks.
"""

import os
import subprocess

import pytest

from courier_worker.host import ContainmentError, terminate_job_tree


class _Proc:
    def __init__(self, alive=True, hang=False):
        self.alive = alive
        self.hang = hang
        self.waits = []

    def poll(self):
        return None if self.alive else 0

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self.hang:
            raise subprocess.TimeoutExpired(cmd="child", timeout=timeout)
        self.alive = False
        return 0


def test_failed_job_terminate_blocks_and_does_not_wait():
    proc = _Proc()
    closed = []
    with pytest.raises(ContainmentError, match="TerminateJobObject"):
        terminate_job_tree("job", proc, grace=5, terminate=lambda job: False,
                           close=lambda job: closed.append(job))
    assert proc.waits == []
    assert closed == []


def test_job_terminate_kills_the_tree_not_only_the_root():
    killed = []

    def terminate(job):
        killed.append(job)
        killed.extend(["root", "grandchild"])
        return True

    proc = _Proc(alive=True)
    closed = []
    terminate_job_tree("job-1", proc, grace=0.2, terminate=terminate,
                       close=lambda job: closed.append(job))
    assert killed == ["job-1", "root", "grandchild"]
    assert proc.poll() == 0
    assert proc.waits == [0.2]
    assert closed == ["job-1"]


def test_process_still_alive_after_job_terminate_blocks():
    closed = []
    with pytest.raises(ContainmentError, match="still alive"):
        terminate_job_tree("job", _Proc(hang=True), grace=0.01, terminate=lambda job: True,
                           close=lambda job: closed.append(job))
    assert closed == []


def test_missing_job_object_blocks():
    with pytest.raises(ContainmentError, match="job object"):
        terminate_job_tree(None, _Proc(), grace=0.1, terminate=lambda job: True, close=lambda job: None)


@pytest.mark.skipif(
    os.name != "nt",
    reason="no Windows runner: kernel32 Job Object kill is not executed on this Linux host",
)
def test_windows_job_object_kills_grandchild(tmp_path):
    import sys
    import time

    import psutil

    from courier_worker import host as H

    me = psutil.Process()
    before = {p.pid for p in me.children(recursive=True)}
    code = ("import subprocess, sys, time; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
            "time.sleep(60)")
    run = H._spawn_contained([sys.executable, "-c", code], str(tmp_path), "job")
    time.sleep(0.5)
    run.terminate_tree(grace=2.0)
    leftovers = [p.pid for p in me.children(recursive=True) if p.pid not in before]
    assert leftovers == []
