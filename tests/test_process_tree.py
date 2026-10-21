"""Tests for hardened process tree termination and orphan prevention (S05)."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from courier_core.process_supervisor import ProcessSupervisor
from courier_core.process_tree import (
    get_process_descendants,
    is_process_alive,
    kill_process_tree,
)


def test_kill_process_tree_ignores_invalid_and_self():
    # Should safely return without error or action
    kill_process_tree(None)  # type: ignore
    kill_process_tree(-1)
    kill_process_tree(0)
    kill_process_tree(os.getpid())  # Must never kill itself!


def test_kill_process_tree_terminates_single_child():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid = proc.pid
    assert is_process_alive(pid)

    kill_process_tree(proc)

    # Allow brief window for OS reaping
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and is_process_alive(pid):
        time.sleep(0.05)

    assert not is_process_alive(pid), f"Process {pid} should have been terminated"


def test_kill_process_tree_terminates_grandchild_process_tree(tmp_path: Path):
    pid_file = tmp_path / "grandchild.pid"
    script = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"with open(r'{pid_file}', 'w') as f: f.write(str(child.pid))\n"
        "time.sleep(60)\n"
    )

    parent_proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    parent_pid = parent_proc.pid

    # Wait for grandchild pid file to be written
    deadline = time.monotonic() + 5.0
    grandchild_pid = None
    while time.monotonic() < deadline:
        if pid_file.exists() and pid_file.stat().st_size > 0:
            try:
                grandchild_pid = int(pid_file.read_text(encoding="utf-8").strip())
                break
            except ValueError:
                pass
        time.sleep(0.05)

    assert grandchild_pid is not None, "Grandchild failed to start"
    assert is_process_alive(parent_pid)
    assert is_process_alive(grandchild_pid)

    # Terminate process tree targeting parent
    kill_process_tree(parent_proc)

    # Verify both parent AND grandchild are dead
    reap_deadline = time.monotonic() + 5.0
    while time.monotonic() < reap_deadline:
        if not is_process_alive(parent_pid) and not is_process_alive(grandchild_pid):
            break
        time.sleep(0.05)

    assert not is_process_alive(parent_pid), f"Parent {parent_pid} was not killed"
    assert not is_process_alive(grandchild_pid), f"Grandchild {grandchild_pid} was orphaned!"


def test_process_supervisor_stop_process_terminates_tree(tmp_path: Path):
    supervisor = ProcessSupervisor()
    pid_file = tmp_path / "supervisor_child.pid"
    script = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"with open(r'{pid_file}', 'w') as f: f.write(str(child.pid))\n"
        "time.sleep(60)\n"
    )

    supervisor.register_process("test-worker", [sys.executable, "-c", script])
    assert supervisor.start_process("test-worker")

    # Wait for child to spawn
    deadline = time.monotonic() + 5.0
    child_pid = None
    while time.monotonic() < deadline:
        if pid_file.exists() and pid_file.stat().st_size > 0:
            try:
                child_pid = int(pid_file.read_text(encoding="utf-8").strip())
                break
            except ValueError:
                pass
        time.sleep(0.05)

    assert child_pid is not None

    # Stop process via supervisor
    assert supervisor.stop_process("test-worker", timeout=2.0)

    # Verify grandchild is also dead
    reap_deadline = time.monotonic() + 5.0
    while time.monotonic() < reap_deadline and is_process_alive(child_pid):
        time.sleep(0.05)

    assert not is_process_alive(child_pid), f"Supervisor child {child_pid} was orphaned!"
