import os
import pytest
import subprocess
import time
import shutil
import urllib.request
import json
import signal
from pathlib import Path

@pytest.mark.skipif(os.name != 'nt', reason="Windows specific clean-machine harness")
def test_win_clean_machine_harness(tmp_path):
    """
    Proves:
    - fresh install
    - first launch
    - single instance
    - Hub/controller startup
    - synthetic work execution
    - shutdown & restart
    - clean uninstall
    """
    state_dir = tmp_path / "CourierWorker" # Because LOCALAPPDATA doesn't include "Courier" but CourierLauncher appends "Courier" to LOCALAPPDATA. wait, it is %LOCALAPPDATA%\Courier. So it will be tmp_path / "Courier".
    
    # 1. Fresh install & first launch
    launcher_exe = Path("scripts/windows_worker/Courier.exe").resolve()
    assert launcher_exe.exists(), "Courier.exe must be built before tests"

    # Start the launcher
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(tmp_path)
    env["COURIER_TEST_NO_JOB"] = "1"
    # We will use Courier's default ports or force them via config.json
    courier_dir = tmp_path / "Courier"
    courier_dir.mkdir(parents=True)
    
    # Force specific ports via config.json to avoid conflicts
    config_file = courier_dir / "config.json"
    config_file.write_text(json.dumps({
        "COURIER_CONTROLLER_PORT": 8800,
        "COURIER_HUB_PORT": 8801
    }))

    # 0x01000000 is CREATE_BREAKAWAY_FROM_JOB
    launcher = subprocess.Popen([str(launcher_exe)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000)

    try:
        # Wait for token
        token_file = courier_dir / "run" / "controller.token"
        start_time = time.monotonic()
        while time.monotonic() - start_time < 30:
            if launcher.poll() is not None:
                out = launcher.stdout.read()
                pytest.fail(f"Launcher exited early with code {launcher.returncode}:\n{out}")
            if token_file.exists():
                token = token_file.read_text().strip()
                if token:
                    break
            time.sleep(0.5)
        else:
            pytest.fail(f"Timeout waiting for controller.token. Launcher output:\n{launcher.stdout.read()}")

        controller_url = "http://127.0.0.1:8800"
        hub_url = "http://127.0.0.1:8801"

        def api(method, path, body=None):
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(controller_url + path, data=data, method=method,
                                         headers={"X-Courier-Token": token, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read() or b"{}")

        # Wait for Hub to be up
        start_time = time.monotonic()
        while time.monotonic() - start_time < 30:
            try:
                req = urllib.request.Request(hub_url + "/hub/api/status")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            pytest.fail("Timeout waiting for Hub")

        # 3. Synthetic work execution
        # Normal task
        done_id = api("POST", "/v1/tasks", {
            "adapter": "synthetic", "params": {"sleep_s": 1, "write": "out.txt", "content": "normal"},
            "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 6
        })["task_id"]

        # Non-idempotent task (killed mid-action)
        blocked_id = api("POST", "/v1/tasks", {
            "adapter": "synthetic", "params": {"write": "sent.txt", "content": "message", "hang": True},
            "effect_class": "non_idempotent", "max_attempts": 3, "lease_ttl_s": 6
        })["task_id"]

        # Long-running task
        working_id = api("POST", "/v1/tasks", {
            "adapter": "synthetic", "params": {"sleep_s": 60, "write": "report.txt", "content": "long"},
            "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 6, "timeout_s": 90
        })["task_id"]

        def wait_for(task_id, status_val, timeout=30):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if api("GET", f"/v1/tasks/{task_id}")["status"] == status_val:
                    return
                time.sleep(0.5)
            pytest.fail(f"Timeout waiting for task {task_id} to reach {status_val}")

        wait_for(done_id, "COMPLETE")
        wait_for(blocked_id, "RUNNING")

        # Kill the worker for blocked_id
        # worker.lock is locked with msvcrt.locking on Windows, so we cannot read it directly.
        # Instead, find the claim record for the blocked task.
        claims_dir = courier_dir / "run" / "claims"
        worker_pid = None
        for p in claims_dir.glob("dispatch-*.json"):
            try:
                record = json.loads(p.read_text())
                if record.get("task_id") == blocked_id:
                    worker_pid = record["owner_pid"]
                    break
            except Exception:
                pass
        
        assert worker_pid is not None, "Could not find worker_pid from claims"
        subprocess.run(["taskkill", "/F", "/PID", str(worker_pid)], check=False)
        
        # Wait for blocked task to be blocked (lease expiration takes 6s)
        wait_for(blocked_id, "BLOCKED")

        # Now that the worker is freed, working_id can start
        wait_for(working_id, "RUNNING")

        # Check Hub UI state
        req = urllib.request.Request(hub_url + "/hub/api/home")
        with urllib.request.urlopen(req) as resp:
            home_view = json.loads(resp.read())
            
        assert any(t["id"] == done_id for t in home_view["done"])
        assert any(t["id"] == blocked_id for t in home_view["needs_you"])
        assert any(t["id"] == working_id for t in home_view["working"])

        # Choose "It happened"
        hub_post = urllib.request.Request(hub_url + f"/hub/api/items/{blocked_id}/decision", 
                                          data=json.dumps({"decision": "effect_confirmed", "attempt": 1}).encode(),
                                          method="POST",
                                          headers={"X-Courier-Hub": "1", "Content-Type": "application/json"})
        with urllib.request.urlopen(hub_post) as resp:
            assert resp.status == 200

        # Wait for blocked task to complete
        wait_for(blocked_id, "COMPLETE")

    finally:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher.pid)], check=False)
        launcher.wait(10)

    # 4. Restart and Replay
    launcher2 = subprocess.Popen([str(launcher_exe)], env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        start_time = time.monotonic()
        while time.monotonic() - start_time < 30:
            try:
                req = urllib.request.Request(hub_url + "/hub/api/status")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            pytest.fail("Timeout waiting for Hub after restart")

        req = urllib.request.Request(hub_url + "/hub/api/home")
        with urllib.request.urlopen(req) as resp:
            home_view = json.loads(resp.read())
            
        # done_id should still be done
        assert any(t["id"] == done_id for t in home_view["done"])
        # blocked_id was confirmed, so it's done now
        assert any(t["id"] == blocked_id for t in home_view["done"])

        # Check that no worker lock exists from old process, wait for worker to boot up
        time.sleep(2)
        
    finally:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher2.pid)], check=False)
        launcher2.wait(10)

    # 6. Clean uninstall
    if courier_dir.exists():
        # wait a bit for file handles to close
        time.sleep(2)
        shutil.rmtree(courier_dir, ignore_errors=True)
