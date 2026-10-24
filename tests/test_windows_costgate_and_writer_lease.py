"""Comprehensive verification for Windows CostGate and Writer-Lease invariants.

Proves:
1. Windows CostGate:
   - Tasks with authorized 0.0 EUR / included_quota are UNBLOCKED and executed.
   - Tasks with unknown cost (missing, unknown_cost=True, cost_class='unknown') fail-closed (BLOCKED).
   - Tasks with unauthorized spend (estimated_cost_eur > 0.0, NaN, negative) fail-closed (BLOCKED).
2. Windows Writer-Lease:
   - Single-writer mutual exclusion: while instance A holds the lock, instance B cannot acquire.
   - Clean release: release_lock frees the lock and unlinks the file.
   - Safe handover: instance B can acquire immediately after instance A releases.
"""
import importlib.util
import json
import os
from pathlib import Path
import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "daemon.py"


def load_daemon(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    spec = importlib.util.spec_from_file_location("win_daemon_costgate_lease_test", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    return daemon


# -- CostGate Invariants --

def test_windows_costgate_allows_authorized_zero_cost(tmp_path, monkeypatch):
    """Proves CostGate UNBLOCKS valid zero-cost Windows tasks."""
    daemon = load_daemon(tmp_path, monkeypatch)
    config = {"WORKER_ID": "WIN-01"}

    # Mock actual PowerShell invocation to observe CostGate admission
    executed = []
    class DummyProc:
        pid = 1234
        returncode = 0
        def communicate(self, timeout=None):
            return ("output-ok", "")
    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *a, **k: DummyProc())

    # Task 1: explicit 0.0 EUR
    task1 = {"task_id": "win-001", "instruction": "Write-Host 'ok'", "estimated_cost_eur": 0.0}
    res1 = daemon.run_task(task1, config)
    assert res1["status"] == "SUCCESS"
    assert res1.get("blocked") is not True

    # Task 2: included_quota with an explicit 0.0 estimate
    task2 = {"task_id": "win-002", "instruction": "Write-Host 'ok'", "cost_class": "included_quota",
             "estimated_cost_eur": 0.0}
    res2 = daemon.run_task(task2, config)
    assert res2["status"] == "SUCCESS"
    assert res2.get("blocked") is not True


@pytest.mark.parametrize("task", [
    {"cost_class": "included_quota"},
    {"routing_decision": {"COST_CLASS": "included_quota"}},
    {"cost_class": "INCLUDED_QUOTA"},
])
def test_windows_costgate_blocks_included_quota_without_an_estimate(tmp_path, monkeypatch, task):
    """Founder decision 23.10: an included quota is not a known cost; without an estimate it is UNKNOWN_COST."""
    daemon = load_daemon(tmp_path, monkeypatch)
    started = []
    monkeypatch.setattr(daemon.subprocess, "Popen", lambda *a, **k: started.append(a))
    res = daemon.run_task(dict(task, task_id="win-iq", instruction="Write-Host 'ok'"), {"WORKER_ID": "WIN-01"})
    assert res["status"] == "FAILED" and res["blocked"] is True
    assert "COST_GATE_DENIED: UNKNOWN_COST" in res["stderr"]
    assert started == []                                    # blocked before PowerShell starts


def test_windows_costgate_blocks_unknown_or_unapproved_cost(tmp_path, monkeypatch):
    """Proves CostGate blocks unapproved spend or unknown cost fail-closed."""
    daemon = load_daemon(tmp_path, monkeypatch)
    config = {"WORKER_ID": "WIN-01"}

    # 1. Unknown cost flag
    res_flag = daemon.run_task({"task_id": "t1", "instruction": "dir", "unknown_cost": True}, config)
    assert res_flag["status"] == "FAILED"
    assert res_flag["blocked"] is True
    assert "COST_GATE_DENIED: UNKNOWN_COST" in res_flag["stderr"]

    # 2. Unknown cost class
    res_class = daemon.run_task({"task_id": "t2", "instruction": "dir", "cost_class": "unknown"}, config)
    assert res_class["status"] == "FAILED"
    assert res_class["blocked"] is True
    assert "COST_GATE_DENIED: UNKNOWN_COST" in res_class["stderr"]

    # 3. Missing cost without included_quota
    res_missing = daemon.run_task({"task_id": "t3", "instruction": "dir"}, config)
    assert res_missing["status"] == "FAILED"
    assert res_missing["blocked"] is True
    assert "COST_GATE_DENIED: UNKNOWN_COST" in res_missing["stderr"]

    # 4. Unauthorized positive spend
    res_paid = daemon.run_task({"task_id": "t4", "instruction": "dir", "estimated_cost_eur": 5.0}, config)
    assert res_paid["status"] == "FAILED"
    assert res_paid["blocked"] is True
    assert "COST_GATE_DENIED" in res_paid["stderr"]

    # 5. Invalid NaN / non-numeric
    res_nan = daemon.run_task({"task_id": "t5", "instruction": "dir", "estimated_cost_eur": float("nan")}, config)
    assert res_nan["status"] == "FAILED"
    assert res_nan["blocked"] is True
    assert "COST_GATE_DENIED" in res_nan["stderr"]


# -- Writer-Lease Invariants --

def test_windows_writer_lease_single_writer_exclusion(tmp_path, monkeypatch):
    """Proves single-writer mutual exclusion: no concurrent writer while lock is held."""
    daemon = load_daemon(tmp_path, monkeypatch)
    worker_id = f"WIN-TEST-{os.getpid()}"

    # First acquisition succeeds
    lock1 = daemon.acquire_lock(worker_id)
    assert lock1 is not None
    assert Path(lock1).exists()

    try:
        # Second acquisition for the same worker_id fails (lock held)
        lock2 = daemon.acquire_lock(worker_id)
        assert lock2 is None, "Second writer must be blocked while first writer holds lease"
    finally:
        # Clean release
        daemon.release_lock(lock1)

    assert not Path(lock1).exists() or daemon._lock_fd is None

    # After release, re-acquisition succeeds immediately
    lock3 = daemon.acquire_lock(worker_id)
    assert lock3 is not None
    daemon.release_lock(lock3)


def test_windows_writer_lease_cross_process_mutual_exclusion(tmp_path, monkeypatch):
    """Proves cross-process mutual exclusion: two separate processes cannot hold the lease simultaneously."""
    import subprocess
    import sys
    import time

    daemon = load_daemon(tmp_path, monkeypatch)
    worker_id = f"WIN-XP-{os.getpid()}"

    ready_file = tmp_path / "child.ready"
    stop_file = tmp_path / "child.stop"

    repo_root = str(Path(__file__).resolve().parents[1])
    child_script = """
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from scripts.windows_worker import daemon
worker_id = sys.argv[2]
ready_file = Path(sys.argv[3])
stop_file = Path(sys.argv[4])

lock = daemon.acquire_lock(worker_id)
assert lock is not None, 'Child could not acquire lock'
ready_file.write_text('READY')

# Wait for parent signal to release
deadline = time.monotonic() + 10
while time.monotonic() < deadline and not stop_file.exists():
    time.sleep(0.05)

daemon.release_lock(lock)
"""
    proc = subprocess.Popen([
        sys.executable,
        "-c",
        child_script,
        repo_root,
        worker_id,
        str(ready_file),
        str(stop_file),
    ])
    try:
        # Wait for child to durably hold the lock
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not ready_file.exists():
            time.sleep(0.05)
        assert ready_file.exists(), "Child process failed to acquire lock in time"

        # Parent attempts to acquire same worker_id lock -> MUST fail (None)
        parent_lock = daemon.acquire_lock(worker_id)
        assert parent_lock is None, "Parent must be blocked from acquiring while child holds lock"
    finally:
        # Signal child to release and exit
        stop_file.write_text("STOP")
        proc.wait(timeout=10)

    # After child finishes and releases, parent must now be able to acquire
    parent_lock2 = daemon.acquire_lock(worker_id)
    assert parent_lock2 is not None, "Parent must acquire lock once child has released"
    daemon.release_lock(parent_lock2)


def test_windows_host_executes_under_courier_ledger_writer_lease(tmp_path):
    """Proves the canonical Courier Ledger Writer-Lease (LeaseStore with fencing token)

    on Windows host:
    1. Single active lease per mutable scope with monotonic fencing token.
    2. Competing worker or conflicting workkey is rejected with LeaseConflict while held.
    3. Old holder cannot write with stale token (StaleLease).
    4. Clean release frees the scope and advances fencing token.
    """
    from courier_runtime.lease import LeaseStore, LeaseConflict, StaleLease
    from courier_runtime.hosts import Host, Requirement, select
    
    clock_time = [1000.0]
    def fake_clock():
        return clock_time[0]

    db_path = str(tmp_path / "ledger_lease.db")
    store = LeaseStore(db_path, clock=fake_clock)

    scope = "repo:courier-v1"
    win_host = "win-worker-01"
    other_host = "win-worker-02"

    # 1. Windows worker acquires lease for workkey wk-1
    lease = store.acquire(scope, win_host, "wk-1", ttl_s=30)
    assert lease.holder == win_host
    assert lease.workkey == "wk-1"
    assert lease.token == 1
    assert lease.expires_at == 1030.0

    # 2. Competing worker attempting to claim same scope is REJECTED with LeaseConflict
    with pytest.raises(LeaseConflict):
        store.acquire(scope, other_host, "wk-2", ttl_s=30)

    # 3. Same worker attempting different workkey is ALSO rejected while active
    with pytest.raises(LeaseConflict):
        store.acquire(scope, win_host, "wk-other", ttl_s=30)

    # 4. Valid write check with current token passes
    checked = store.check_write(scope, lease.token)
    assert checked.holder == win_host
    assert checked.token == 1

    # 5. Heartbeat / renewal extends lease
    clock_time[0] += 10.0
    renewed = store.renew(lease, ttl_s=30)
    assert renewed.expires_at == 1040.0

    # 6. Clean release frees the lease
    store.release(renewed)
    assert store.current(scope) is None

    # 7. Next worker can now acquire, fencing token monotonically increments to 2
    lease2 = store.acquire(scope, other_host, "wk-2", ttl_s=30)
    assert lease2.holder == other_host
    assert lease2.token == 2

    # 8. First worker presenting old token 1 is strictly rejected with StaleLease
    with pytest.raises(StaleLease):
        store.check_write(scope, lease.token)

    store.close()


def test_daemon_acquire_lock_integrates_canonical_lease_store(tmp_path, monkeypatch):
    """Proves that scripts.windows_worker.daemon.acquire_lock binds to authority.db LeaseStore."""
    import scripts.windows_worker.daemon as daemon
    from courier_runtime.lease import LeaseStore

    auth_db = tmp_path / "authority.db"
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path)
    monkeypatch.setattr(daemon, "_lease_store", None)
    monkeypatch.setattr(daemon, "_lock_fd", None)
    monkeypatch.setattr(daemon, "_worker_lease", None)

    # 1. Acquire lock
    lock_path = daemon.acquire_lock("worker-test-auth")
    assert lock_path is not None
    assert daemon._worker_lease is not None
    assert daemon._worker_lease.scope == "worker:worker-test-auth"
    assert daemon._worker_lease.token >= 1

    # Check store independently sees the active lease
    store = LeaseStore(str(auth_db))
    current = store.current("worker:worker-test-auth")
    assert current is not None
    assert "worker-test-auth" in current.holder
    store.close()

    # 2. Release lock
    daemon.release_lock(lock_path)
    assert daemon._worker_lease is None

    # Check store sees the lease as released
    store = LeaseStore(str(auth_db))
    assert store.current("worker:worker-test-auth") is None
    store.close()


# -- V8 red team: a task's own label is not a cost; the PowerShell child gets no credentials --

def _capture_popen(daemon, monkeypatch):
    calls = []

    class DummyProc:
        pid = 4321
        returncode = 0

        def communicate(self, timeout=None):
            return ("ok", "")

    def popen(cmd, **kwargs):
        calls.append(kwargs)
        return DummyProc()
    monkeypatch.setattr(daemon.subprocess, "Popen", popen)
    return calls


@pytest.mark.parametrize("instruction", ["codex exec 'fix it'", "& 'C:\\Tools\\claude.exe' -p hi",
                                         "Write-Host x; npx -y @google/gemini-cli", "timeout 30s codex",
                                         "agy -p hi | Out-File o.txt", "npx @openai/codex exec x",
                                         "Start-Process gemini -ArgumentList '-p','x'"])
def test_windows_refuses_an_instruction_that_starts_a_provider_cli(tmp_path, monkeypatch, instruction):
    daemon = load_daemon(tmp_path, monkeypatch)
    calls = _capture_popen(daemon, monkeypatch)
    res = daemon.run_task({"task_id": "win-p", "instruction": instruction, "estimated_cost_eur": 0.0},
                          {"WORKER_ID": "WIN-01"})
    assert res["status"] == "FAILED" and res["blocked"] is True and "PROVIDER_CLI" in res["stderr"]
    assert calls == []


@pytest.mark.parametrize("instruction", ["git commit -m 'fix codex bridge'", "Write-Host \"agy done\"",
                                         "Get-ChildItem C:\\src\\claude\\"])
def test_windows_instruction_that_names_a_provider_as_an_argument_runs(tmp_path, monkeypatch, instruction):
    daemon = load_daemon(tmp_path, monkeypatch)
    calls = _capture_popen(daemon, monkeypatch)
    res = daemon.run_task({"task_id": "win-a", "instruction": instruction, "estimated_cost_eur": 0.0},
                          {"WORKER_ID": "WIN-01"})
    assert res["status"] == "SUCCESS" and len(calls) == 1


def test_windows_powershell_child_has_its_own_empty_profile(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    monkeypatch.setenv("USERPROFILE", "C:\\Users\\worker-sentinel")
    monkeypatch.setenv("CODEX_HOME", "C:\\Users\\worker-sentinel\\.codex")
    monkeypatch.setenv("HTTPS_PROXY", "http://u:p@proxy:8080")
    calls = _capture_popen(daemon, monkeypatch)
    daemon.run_task({"task_id": "win-h", "instruction": "Write-Host ok", "estimated_cost_eur": 0.0},
                    {"WORKER_ID": "WIN-01"})
    env = calls[0]["env"]
    assert "worker-sentinel" not in " ".join(env.values())
    assert env["USERPROFILE"] == env["LOCALAPPDATA"] == env["APPDATA"]
    assert not Path(env["USERPROFILE"]).exists()              # removed after the run
    assert "CODEX_HOME" not in env and "HTTPS_PROXY" not in env


def test_windows_instruction_that_only_mentions_a_word_still_runs(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    calls = _capture_popen(daemon, monkeypatch)
    res = daemon.run_task({"task_id": "win-w", "instruction": "Write-Host 'claudette and geminid'",
                           "estimated_cost_eur": 0.0}, {"WORKER_ID": "WIN-01"})
    assert res["status"] == "SUCCESS" and len(calls) == 1


def test_windows_powershell_child_gets_no_credentials(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    for name in ("COURIER_API_KEY", "COURIER_CONTROLLER_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                 "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(name, "sentinel-not-a-real-value")
    monkeypatch.setenv("SYSTEMROOT", "C:\\Windows")
    calls = _capture_popen(daemon, monkeypatch)
    res = daemon.run_task({"task_id": "win-e", "instruction": "Write-Host 'ok'", "estimated_cost_eur": 0.0},
                          {"WORKER_ID": "WIN-01"})
    assert res["status"] == "SUCCESS"
    env = calls[0]["env"]
    assert "sentinel-not-a-real-value" not in env.values()
    assert env.get("SYSTEMROOT") == "C:\\Windows" and env.get("PATH")
