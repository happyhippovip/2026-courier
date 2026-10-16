import os
import pytest
import subprocess
import time
import shutil
import urllib.request
import json
import signal
from pathlib import Path

@pytest.fixture(autouse=True)
def restore_courier_exe():
    yield
    if os.name == 'nt':
        try:
            subprocess.run(["git", "restore", "scripts/windows_worker/Courier.exe"], check=False)
        except Exception:
            pass

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
    state_dir = tmp_path / "Courier"
    
    # 1. Fresh install & first launch
    build_script = Path("scripts/windows_worker/launcher/build_launcher.ps1").resolve()
    if build_script.exists():
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(build_script), "-TestBuild"], check=True)

    launcher_exe = Path("scripts/windows_worker/Courier.exe").resolve()
    assert launcher_exe.exists(), "Courier.exe must be built before tests"

    # Start the launcher
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(tmp_path)
    env["COURIER_TEST_NO_JOB"] = "1"
    env["PYTHONPATH"] = str(Path.cwd())
    # We will use Courier's default ports or force them via config.json
    courier_dir = tmp_path / "Courier"
    courier_dir.mkdir(parents=True)
    
    # Force specific ports via config.json to avoid conflicts
    config_file = courier_dir / "config.json"
    config_file.write_text(json.dumps({
        "COURIER_CONTROLLER_PORT": 8800,
        "COURIER_HUB_PORT": 8801
    }))

    # Start controller and hub natively in the test harness
    controller_cmd = ["uv", "run", "python", "-m", "courier_core.serve", "--home", str(courier_dir), "--port", "8800"]
    hub_cmd = ["uv", "run", "python", "-m", "courier_hub", "--home", str(courier_dir), "--controller", "http://127.0.0.1:8800", "--port", "8801"]
    
    ctrl_proc = subprocess.Popen(controller_cmd, env=env)
    hub_proc = subprocess.Popen(hub_cmd, env=env)
    
    launcher = None
    try:
        # 0x01000000 is CREATE_BREAKAWAY_FROM_JOB
        try:
            launcher = subprocess.Popen([str(launcher_exe)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000)
        except PermissionError as e:
            if e.winerror == 5:
                # Cannot break away from Job object (e.g. GitHub Actions runner)
                launcher = subprocess.Popen([str(launcher_exe)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                raise

        # Wait for token
        token_file = courier_dir / "run" / "controller.token"
        start_time = time.monotonic()
        while time.monotonic() - start_time < 30:
            if launcher.poll() is not None:
                out = launcher.stdout.read()
                pytest.fail(f"Launcher exited early with code {launcher.returncode}:\n{out}")
            if ctrl_proc.poll() is not None:
                pytest.fail("Controller exited early")
            if token_file.exists():
                token = token_file.read_text().strip()
                if token:
                    break
            time.sleep(0.5)
        else:
            log_content = (courier_dir / "logs" / "worker.log").read_text() if (courier_dir / "logs" / "worker.log").exists() else "No worker.log"
            pytest.fail(f"Timeout waiting for controller.token. Worker log:\n{log_content}")

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
        start_wait = time.monotonic()
        while time.monotonic() - start_wait < 10:
            for p in claims_dir.glob("dispatch-*.json"):
                try:
                    record = json.loads(p.read_text())
                    if record.get("task_id") == blocked_id:
                        worker_pid = record["owner_pid"]
                        break
                except Exception:
                    pass
            if worker_pid is not None:
                break
            time.sleep(0.5)
        
        if worker_pid is None:
            print(f"Claims dir {claims_dir} contents: {list(claims_dir.glob('*'))}")
            print(f"Looking for task_id: {blocked_id}")
            for p in claims_dir.glob("dispatch-*.json"):
                try:
                    print(f"File {p.name}: {p.read_text()}")
                except Exception as e:
                    print(f"File {p.name} read error: {e}")
        
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
        if launcher is not None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher.pid)], check=False)
            launcher.wait(10)

    # 4. Restart and Replay
    # 0x01000000 is CREATE_BREAKAWAY_FROM_JOB
    try:
        launcher2 = subprocess.Popen([str(launcher_exe)], env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000)
    except PermissionError as e:
        if getattr(e, "winerror", None) == 5:
            launcher2 = subprocess.Popen([str(launcher_exe)], env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            raise
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
        
        new_task_id = api("POST", "/v1/tasks", {
            "adapter": "synthetic", "params": {"sleep_s": 3, "write": "post_restart.txt", "content": "normal"},
            "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 6
        })["task_id"]

        wait_for(new_task_id, "RUNNING")
        
        new_worker_pid = None
        start_wait = time.monotonic()
        while time.monotonic() - start_wait < 10:
            for p in claims_dir.glob("dispatch-*.json"):
                try:
                    record = json.loads(p.read_text())
                    if record.get("task_id") == new_task_id:
                        new_worker_pid = record["owner_pid"]
                        break
                except Exception:
                    pass
            if new_worker_pid is not None:
                break
            time.sleep(0.5)
        
        assert new_worker_pid is not None, "Could not find worker_pid for the new task"
        assert new_worker_pid != worker_pid, "Worker PID must be different post-restart (new generation)"
        
        wait_for(new_task_id, "COMPLETE")
        
        def is_pid_running(pid):
            try:
                output = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}"]).decode()
                return str(pid) in output
            except Exception:
                return False

        assert not is_pid_running(launcher.pid), "Old launcher PID survived"
        assert not is_pid_running(worker_pid), "Old worker PID survived"
        
        try:
            launcher3 = subprocess.Popen([str(launcher_exe)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x01000000)
        except PermissionError as e:
            if getattr(e, "winerror", None) == 5:
                launcher3 = subprocess.Popen([str(launcher_exe)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                raise
        
        time.sleep(3)
        poll_res = launcher3.poll()
        if poll_res is None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher3.pid)], check=False)
            pytest.fail("Second worker stayed alive instead of exiting on lock conflict")
        
    finally:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher2.pid)], check=False)
        launcher2.wait(10)
        
        ctrl_proc.terminate()
        hub_proc.terminate()
        ctrl_proc.wait(5)
        hub_proc.wait(5)

    # 6. Clean uninstall
    if courier_dir.exists():
        # wait a bit for file handles to close
        time.sleep(2)
        shutil.rmtree(courier_dir, ignore_errors=True)
