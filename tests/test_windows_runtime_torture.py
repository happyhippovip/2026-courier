import subprocess, sys, time, json, os, uuid, pytest, urllib.request, urllib.error, socket, copy
from pathlib import Path
from tempfile import TemporaryDirectory

HEADERS = {"Authorization": "Bearer test-key-12345", "Content-Type": "application/json"}

def t_assert(condition, message):
    assert condition, message
    print(f"[PASS] {message}")

def test_windows_torture():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        test_port = s.getsockname()[1]
    api_url = f"http://127.0.0.1:{test_port}"

    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "central_state.json"
        
        server_env = os.environ.copy()
        server_env["COURIER_STATE_FILE"] = str(state_file)
        server_env["COURIER_API_KEY"] = "test-key-12345"
        server_env["COURIER_VERIFIER_API_KEY"] = "test-key-12345"
        server_env["PYTHONPATH"] = os.path.abspath(".")
        server_env["PORT"] = str(test_port)
        
        print(f"Starting server on port {test_port}...")
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
            
        print("Server ready.")
        worker_dir = Path("scripts/windows_worker")
        state_dir = worker_dir / "state"
        state_dir.mkdir(exist_ok=True)
        effect_marker = state_dir / "effect_marker.json"
        result_marker = state_dir / "result_marker.json"
        
        # Ensure state markers are clean before test
        if effect_marker.exists(): effect_marker.unlink()
        if result_marker.exists(): result_marker.unlink()
        
        try:
            # 1. Create a dummy task manually
            task_id = "task-win-torture-01"
            payload = {
                "goal_text": "Win Torture",
                "workflow_plan": [
                    {"task_id": task_id, "target_agent": "windows", "mode": "NATIVE", "instruction": "echo test"}
                ]
            }
            res = urllib.request.urlopen(urllib.request.Request(f"{api_url}/goals", method="POST", data=json.dumps(payload).encode(), headers=HEADERS))
            t_assert(res.status == 200, "Goal created")
            goal_id = json.loads(res.read().decode())["goal_id"]

            # Register worker & claim task
            worker_id = "WINDOWS-TORTURE-01"
            reg_payload = {"worker_id": worker_id, "platform": "windows", "capabilities": ["windows"], "cost_class": "low"}
            urllib.request.urlopen(urllib.request.Request(f"{api_url}/workers/register", method="POST", data=json.dumps(reg_payload).encode(), headers=HEADERS))
            
            claim_payload = {"worker_id": worker_id}
            claim_res = urllib.request.urlopen(urllib.request.Request(f"{api_url}/tasks/claim", method="POST", data=json.dumps(claim_payload).encode(), headers=HEADERS))
            claimed_task = json.loads(claim_res.read().decode())["task"]
            t_assert(claimed_task is not None, "Task claimed by worker")
            t_assert(claimed_task["task_id"] == task_id, "Claimed correct task")

            # 2. Test AMBIGUOUS_CRASH recovery
            # Simulate worker crashing during external effect execution while holding claimed_task
            with open(effect_marker, "w") as f:
                json.dump(claimed_task, f)

            print("Starting Windows daemon to process crash marker...")
            import glob, tempfile
            for p in glob.glob(os.path.join(tempfile.gettempdir(), "courier_worker_*.lock")):
                try:
                    os.remove(p)
                except Exception:
                    pass
            daemon_env = os.environ.copy()
            daemon_env["COURIER_SERVER"] = api_url
            daemon_env["COURIER_API_KEY"] = "test-key-12345"
            daemon_env["COURIER_WORKER_ID"] = worker_id
            daemon_env["WORKER_ID"] = worker_id
            daemon_env["PYTHONPATH"] = os.path.abspath(".")
            
            daemon_proc = subprocess.Popen([sys.executable, "-u", str(worker_dir / "daemon.py")], env=daemon_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            t0 = time.time()
            while effect_marker.exists() and time.time() - t0 < 8:
                time.sleep(0.1)
            time.sleep(0.5)
            daemon_proc.terminate()
            stdout, _ = daemon_proc.communicate(timeout=2)
            
            print("Daemon STDOUT (1):\n" + stdout)
            
            t_assert(not effect_marker.exists(), "Effect marker unlinked after recovery")
            t_assert("Found ambiguous crash marker" in stdout, "Daemon detected crash marker")
            
            state_data = json.loads(state_file.read_text())
            task = state_data["tasks"][task_id]
            print(f"Task status after crash recovery: {task.get('status')}")
            t_assert(task.get("status") == "HUMAN_REQUIRED", "Task transitioned to HUMAN_REQUIRED")

            # 3. Test DUPLICATE RESULT (Idempotency)
            fake_result = copy.deepcopy(task["result"])
            with open(result_marker, "w") as f:
                json.dump(fake_result, f)
                
            print("Restarting daemon to process unsent result marker...")
            for p in glob.glob(os.path.join(tempfile.gettempdir(), "courier_worker_*.lock")):
                try:
                    os.remove(p)
                except Exception:
                    pass
            daemon_proc2 = subprocess.Popen([sys.executable, "-u", str(worker_dir / "daemon.py")], env=daemon_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            t0 = time.time()
            while result_marker.exists() and time.time() - t0 < 8:
                time.sleep(0.1)
            time.sleep(0.5)
            daemon_proc2.terminate()
            stdout2, _ = daemon_proc2.communicate(timeout=2)
            
            print("Daemon STDOUT (2):\n" + stdout2)
            
            t_assert(not result_marker.exists(), "Result marker unlinked after recovery")
            t_assert("Found unsent result marker" in stdout2, "Daemon detected unsent result")
            t_assert("Result posted" in stdout2 or "already acknowledged" in stdout2 or "ACK_DUPLICATE" in stdout2, "Duplicate result handled safely")

        finally:
            server_proc.terminate()
            server_proc.wait()
            if effect_marker.exists(): effect_marker.unlink()
            if result_marker.exists(): result_marker.unlink()

if __name__ == '__main__':
    test_windows_torture()
