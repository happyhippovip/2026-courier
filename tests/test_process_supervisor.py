import json
import sys
import time
import pytest
from pathlib import Path
from courier_core.process_supervisor import (
    ProcessSupervisor,
    ManagedProcess,
    ProcessStatus,
    RestartPolicy,
)


def test_process_start_and_normal_completion():
    supervisor = ProcessSupervisor()
    cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]

    supervisor.register_process("p-clean", cmd, restart_policy=RestartPolicy.NEVER)
    supervisor.start_process("p-clean")

    proc = supervisor.get_process("p-clean")
    if proc.popen:
        proc.popen.wait(timeout=5.0)
    supervisor.poll_and_recover()
    assert proc.status == ProcessStatus.COMPLETED
    assert proc.restart_count == 0


def test_process_crash_triggers_auto_restart():
    supervisor = ProcessSupervisor(backoff_base_seconds=0.05)
    # Exits with 1
    cmd = [sys.executable, "-c", "import sys; sys.exit(1)"]

    supervisor.register_process("p-flaky", cmd, restart_policy=RestartPolicy.ON_FAILURE, max_restarts=2)
    supervisor.start_process("p-flaky")

    proc = supervisor.get_process("p-flaky")
    if proc.popen:
        proc.popen.wait(timeout=3.0)
    supervisor.poll_and_recover()

    # First crash should trigger a restart
    assert proc.restart_count >= 1
    assert proc.status in (ProcessStatus.RUNNING, ProcessStatus.RESTARTING, ProcessStatus.COMPLETED)


def test_restart_exhaustion():
    supervisor = ProcessSupervisor(backoff_base_seconds=0.01)
    cmd = [sys.executable, "-c", "import sys; sys.exit(42)"]

    supervisor.register_process("p-doomed", cmd, restart_policy=RestartPolicy.ON_FAILURE, max_restarts=1)
    supervisor.start_process("p-doomed")

    proc = supervisor.get_process("p-doomed")
    # Wait for initial process to finish
    if proc.popen:
        proc.popen.wait(timeout=3.0)
    supervisor.poll_and_recover()

    # Wait for restarted process to finish
    if proc.popen:
        proc.popen.wait(timeout=3.0)
    supervisor.poll_and_recover()

    assert proc.status == ProcessStatus.EXHAUSTED
    assert proc.restart_count == 1


def test_graceful_stop_and_kill():
    supervisor = ProcessSupervisor()
    # Runs forever
    cmd = [sys.executable, "-c", "import time; time.sleep(30)"]

    supervisor.register_process("p-long", cmd, restart_policy=RestartPolicy.NEVER)
    supervisor.start_process("p-long")

    time.sleep(0.2)
    proc = supervisor.get_process("p-long")
    assert proc.status == ProcessStatus.RUNNING

    supervisor.stop_process("p-long", timeout=1.0)
    assert proc.status == ProcessStatus.STOPPED


def test_restart_policy_never():
    supervisor = ProcessSupervisor()
    cmd = [sys.executable, "-c", "import sys; sys.exit(1)"]

    supervisor.register_process("p-norestart", cmd, restart_policy=RestartPolicy.NEVER)
    supervisor.start_process("p-norestart")

    proc = supervisor.get_process("p-norestart")
    if proc.popen:
        proc.popen.wait(timeout=5.0)
    supervisor.poll_and_recover()
    assert proc.status == ProcessStatus.CRASHED
    assert proc.restart_count == 0


def test_exponential_backoff_defers_spawn_until_next_restart_time():
    supervisor = ProcessSupervisor(backoff_base_seconds=5.0)
    cmd = [sys.executable, "-c", "import sys; sys.exit(1)"]
    supervisor.register_process("p-backoff", cmd, restart_policy=RestartPolicy.ON_FAILURE, max_restarts=2)
    supervisor.start_process("p-backoff")
    proc = supervisor.get_process("p-backoff")
    if proc.popen:
        proc.popen.wait(timeout=3.0)
    supervisor.poll_and_recover()
    assert proc.status == ProcessStatus.RESTARTING
    assert proc.popen is None
    assert proc.next_restart_time > time.time() + 1.0


def test_cli_invocation(tmp_path):
    import subprocess
    import sys

    manifest_file = tmp_path / "supervisor_config.json"
    manifest_file.write_text(
        json.dumps({
            "processes": [
                {
                    "proc_id": "test-cli-proc",
                    "command": [sys.executable, "-c", "print('hello from cli')"],
                    "restart_policy": "NEVER"
                }
            ]
        }),
        encoding="utf-8"
    )

    cmd = [
        sys.executable,
        "-m",
        "courier_core.process_supervisor",
        "run-once",
        "--config",
        str(manifest_file),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = json.loads(proc.stdout)
    assert out["status"] == "SUCCESS"
    assert "test-cli-proc" in out["results"]
