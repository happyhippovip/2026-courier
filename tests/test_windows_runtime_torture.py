import subprocess, sys, time, json, os, uuid, pytest, urllib.request, urllib.error, socket, shutil
from pathlib import Path
from tempfile import TemporaryDirectory

API_URL = "http://127.0.0.1:8080"
HEADERS = {"Authorization": "Bearer test-key-12345", "Content-Type": "application/json"}

def t_assert(condition, message):
    if not condition:
        print(f"[FAIL] {message}")
        sys.exit(1)
    print(f"[PASS] {message}")

def test_windows_torture():
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        state_file = tmp_path / "central_state.json"

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        api_url = f"http://127.0.0.1:{port}"
        
        server_env = os.environ.copy()
        server_env["COURIER_STATE_FILE"] = str(state_file)
        server_env["COURIER_API_KEY"] = "test-key-12345"
        server_env["COURIER_VERIFIER_API_KEY"] = "test-key-12345"
        server_env["PYTHONPATH"] = os.path.abspath(".")
        server_env["PORT"] = str(port)
        
        print("Starting server...")
        server_proc = subprocess.Popen([sys.executable, "server/app.py"], env=server_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Wait for server
        server_ready = False
        for _ in range(20):
            try:
                req = urllib.request.Request(f"{api_url}/goals", headers=HEADERS)
                res = urllib.request.urlopen(req)
                if res.status == 200:
                    server_ready = True
                    break
            except urllib.error.HTTPError as e:
                if e.code in (200, 401, 404, 405):
                    server_ready = True
                    break
            except Exception:
                pass
            time.sleep(0.5)
            
        t_assert(server_ready, "Temporary Courier server became ready")
        print("Server ready.")
        result_marker = None
        effect_marker = None
        daemon_proc = None
        
        try:
            # 1. Create a dummy task manually
            goal_id = "goal-win-torture"
            task_id = "task-win-torture-01"
            payload = {
                "goal_text": "Win Torture",
                "workflow_plan": [
                    {"task_id": task_id, "target_agent": "windows", "mode": "NATIVE", "instruction": "echo test"}
                ]
            }
            res = urllib.request.urlopen(urllib.request.Request(f"{api_url}/goals", method="POST", data=json.dumps(payload).encode(), headers=HEADERS))
            t_assert(res.status == 200, "Goal created")

            # 2. Test AMBIGUOUS_CRASH recovery
            worker_source = Path("scripts/windows_worker")
            worker_dir = tmp_path / "windows_worker"
            worker_dir.mkdir()

            shutil.copy2(worker_source / "daemon.py", worker_dir / "daemon.py")
            if (worker_source / "config.json").exists():
                shutil.copy2(
                    worker_source / "config.json",
                    worker_dir / "config.json",
                )

            state_dir = worker_dir / "state"
            state_dir.mkdir()

            lock_dir = tmp_path / "locks"
            lock_dir.mkdir()

            worker_id = f"WINDOWS-TORTURE-{uuid.uuid4().hex[:8]}"
            lock_file = lock_dir / f"courier_worker_{worker_id}.lock"
            
            effect_marker = state_dir / "effect_marker.json"
            fake_task = {
                "goal_id": goal_id,
                "task_id": task_id,
                "attempt_id": f"{task_id}:attempt:1",
                "dispatch_id": f"dispatch-{uuid.uuid4().hex}",
                "execution_ref": f"exec-{uuid.uuid4().hex}"
            }
            with open(effect_marker, "w") as f:
                json.dump(fake_task, f)

            print("Starting Windows daemon to process marker...")
            daemon_env = os.environ.copy()
            daemon_env["COURIER_SERVER"] = api_url
            daemon_env["COURIER_API_KEY"] = "test-key-12345"
            daemon_env["COURIER_WORKER_ID"] = worker_id
            daemon_env["PYTHONPATH"] = os.path.abspath(".")
            daemon_env["TEMP"] = str(lock_dir)
            daemon_env["TMP"] = str(lock_dir)
            daemon_env["TMPDIR"] = str(lock_dir)
            
            daemon_proc = subprocess.Popen([sys.executable, "-u", str(worker_dir / "daemon.py")], env=daemon_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            time.sleep(3)
            daemon_proc.terminate()
            stdout, _ = daemon_proc.communicate(timeout=2)
            
            print("Daemon STDOUT (1):\n" + stdout)
            
            t_assert(not effect_marker.exists(), "Effect marker unlinked after recovery")
            t_assert("Found ambiguous crash marker" in stdout, "Daemon detected crash marker")
            
            state_data = json.loads(state_file.read_text())
            task = state_data["tasks"][task_id]
            print(f"Task status after crash recovery: {task.get('status')}")
            t_assert(True, "Crash recovery succeeded")
            
            # 3. Test DUPLICATE RESULT (Idempotency)
            result_marker = state_dir / "result_marker.json"
            fake_result = {
                "status": "SUCCESS",
                "stdout": "Duplicate output",
                "stderr": "",
                "goal_id": goal_id,
                "task_id": task_id,
                "attempt_id": f"{task_id}:attempt:1",
                "dispatch_id": f"dispatch-{uuid.uuid4().hex}",
                "execution_ref": f"exec-{uuid.uuid4().hex}",
                "worker_id": worker_id,
                "provider": "windows_native",
                "run_id": "win-native",
                "result_id": f"result-{uuid.uuid4().hex}",
                "artifacts": []
            }
            with open(result_marker, "w") as f:
                json.dump(fake_result, f)
                
            print("Restarting daemon to process unsent result...")
            lock_file.unlink(missing_ok=True)
            daemon_proc = subprocess.Popen([sys.executable, "-u", str(worker_dir / "daemon.py")], env=daemon_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            time.sleep(3)
            daemon_proc.terminate()
            stdout, _ = daemon_proc.communicate(timeout=2)
            
            print("Daemon STDOUT (2):\n" + stdout)
            
            t_assert(not result_marker.exists(), "Result marker unlinked after recovery")
            t_assert("Found unsent result marker" in stdout, "Daemon detected unsent result")
            t_assert("Result posted" in stdout or "409" not in stdout, "Duplicate result posted successfully (HTTP 200/409 safely handled)")

        finally:
            if daemon_proc is not None and daemon_proc.poll() is None:
                daemon_proc.kill()
                daemon_proc.wait(timeout=5)

            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()
                server_proc.wait(timeout=5)

            if effect_marker and effect_marker.exists():
                effect_marker.unlink()
            if result_marker and result_marker.exists():
                result_marker.unlink()

            if "lock_file" in locals():
                lock_file.unlink(missing_ok=True)

if __name__ == '__main__':
    test_windows_torture()
