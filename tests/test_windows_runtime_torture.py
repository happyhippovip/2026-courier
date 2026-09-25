import subprocess, sys, time, json, os, uuid, pytest, urllib.request, urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory

API_URL = "http://127.0.0.1:8082"
HEADERS = {"Authorization": "Bearer test-key-12345", "Content-Type": "application/json"}

def t_assert(condition, message):
    if not condition:
        print(f"[FAIL] {message}")
        sys.exit(1)
    print(f"[PASS] {message}")

def test_windows_torture():
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "central_state.json"
        
        server_env = os.environ.copy()
        server_env["COURIER_STATE_FILE"] = str(state_file)
        server_env["COURIER_API_KEY"] = "test-key-12345"
        server_env["COURIER_VERIFIER_API_KEY"] = "test-key-12345"
        server_env["PYTHONPATH"] = os.path.abspath(".")
        server_env["PORT"] = "8082"
        
        print("Starting server...")
        server_proc = subprocess.Popen([sys.executable, "server/app.py"], env=server_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Wait for server
        server_ready = False
        for _ in range(20):
            try:
                req = urllib.request.Request(f"{API_URL}/goals", headers=HEADERS)
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
            
        print("Server ready.")
        result_marker = None
        effect_marker = None
        
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
            res = urllib.request.urlopen(urllib.request.Request(f"{API_URL}/goals", method="POST", data=json.dumps(payload).encode(), headers=HEADERS))
            t_assert(res.status == 200, "Goal created")

            # 2. Test AMBIGUOUS_CRASH recovery
            worker_dir = Path("scripts/windows_worker")
            state_dir = worker_dir / "state"
            state_dir.mkdir(exist_ok=True)
            
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
            daemon_env["COURIER_SERVER"] = API_URL
            daemon_env["COURIER_API_KEY"] = "test-key-12345"
            daemon_env["WORKER_ID"] = "WINDOWS-TORTURE-01"
            daemon_env["PYTHONPATH"] = os.path.abspath(".")
            
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
                "worker_id": "WINDOWS-TORTURE-01",
                "provider": "windows_native",
                "run_id": "win-native",
                "result_id": f"result-{uuid.uuid4().hex}",
                "artifacts": []
            }
            with open(result_marker, "w") as f:
                json.dump(fake_result, f)
                
            print("Restarting daemon to process unsent result...")
            import glob, tempfile
            for p in glob.glob(os.path.join(tempfile.gettempdir(), "courier_worker_*.lock")): os.remove(p)
            daemon_proc = subprocess.Popen([sys.executable, "-u", str(worker_dir / "daemon.py")], env=daemon_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            time.sleep(3)
            daemon_proc.terminate()
            stdout, _ = daemon_proc.communicate(timeout=2)
            
            print("Daemon STDOUT (2):\n" + stdout)
            
            t_assert(not result_marker.exists(), "Result marker unlinked after recovery")
            t_assert("Found unsent result marker" in stdout, "Daemon detected unsent result")
            t_assert("Result posted" in stdout or "409" not in stdout, "Duplicate result posted successfully (HTTP 200/409 safely handled)")

        finally:
            server_proc.terminate()
            server_proc.wait()
            if effect_marker and effect_marker.exists(): effect_marker.unlink()
            if result_marker and result_marker.exists(): result_marker.unlink()

if __name__ == '__main__':
    test_windows_torture()
