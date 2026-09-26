#!/usr/bin/env python3
"""Targeted test proving limit_wrapper.sh signal trap kills child process on SIGTERM."""

from pathlib import Path
import subprocess
import time
import psutil

ROOT = Path(__file__).resolve().parent.parent


def test_limit_wrapper_cleans_up_child_on_terminate():
    wrapper = ROOT / "scripts" / "mac_worker" / "limit_wrapper.sh"
    proc = subprocess.Popen(["bash", str(wrapper), "sleep", "30"])
    try:
        # Allow wrapper and child sleep process to start
        time.sleep(0.5)
        p = psutil.Process(proc.pid)
        children = p.children(recursive=True)
        assert len(children) > 0, "Wrapper should have spawned child process"
        child = children[0]
        assert child.is_running()

        # Terminate wrapper
        proc.terminate()
        proc.wait(timeout=5)
        time.sleep(0.5)

        # Child process should have been terminated by trap
        assert not child.is_running(), f"Child process {child.pid} was orphaned and leaked!"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
