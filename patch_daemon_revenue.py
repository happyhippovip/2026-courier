import re
import os

filepath = r"C:\Users\lol\2026-workspace\courier\scripts\windows_worker\daemon.py"
with open(filepath, "r") as f:
    content = f.read()

# Add capabilities
content = content.replace('"capabilities": ["windows", "antigravity"]', '"capabilities": ["windows", "antigravity", "revenue_safety_audit"]')

new_run_task_prefix = """def run_task(task, config):
    write_log(f"Running task {task['task_id']}...")
    
    if task.get("type") == "revenue_safety_audit" or "revenue_safety_audit" in task.get("capabilities", []):
        write_log("Executing revenue_v1_safety_baseline.py worker...")
        work_dir = STATE_DIR / task['task_id']
        if work_dir.exists():
            import shutil
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True)
        task_file = work_dir / "task.json"
        with open(task_file, "w") as f:
            json.dump(task, f)
            
        cmd = [sys.executable, str(BASE_DIR.parent / "revenue_v1_safety_baseline.py"), "worker", str(task_file), str(work_dir)]
        try:
            import subprocess
            result_raw = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            result_data = json.loads(result_raw.decode("utf-8"))
            
            import zipfile, base64
            zip_path = work_dir / "revenue_artifacts.zip"
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                if (work_dir / "report.json").exists():
                    zipf.write(work_dir / "report.json", "report.json")
                if (work_dir / "report.md").exists():
                    zipf.write(work_dir / "report.md", "report.md")
                    
            with open(zip_path, "rb") as f:
                artifact_bytes = f.read()
                
            import hashlib
            artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
            artifact_b64 = base64.b64encode(artifact_bytes).decode('utf-8')
            
            return {
                "status": "SUCCESS" if result_data.get("status") == "PASS" else "FAILED",
                "run_id": "win-revenue-native",
                "artifact_name": "revenue_artifacts.zip",
                "artifact_sha256": artifact_sha,
                "artifact_content_base64": artifact_b64,
                "result_data": result_data,
                "raw_result": result_data
            }
        except subprocess.CalledProcessError as e:
            return {
                "status": "FAILED",
                "run_id": "win-revenue-native",
                "stderr": e.output.decode('utf-8', errors='ignore')
            }
"""

# Replace the run_task signature and the first write_log, falling through if not revenue
content = re.sub(
    r'def run_task\(task, config\):\n\s+write_log\(f"Running task \{task\[\'task_id\'\]\}..."\)',
    new_run_task_prefix,
    content
)

# Wait, `loop()` in daemon.py creates `pending_payload` manually with:
# "artifacts": artifact_evidence
# But the revenue payload uses `artifact_name`, `artifact_sha256`, `artifact_content_base64` and `result_data`.
# Let's modify loop() to just merge whatever is in result into pending_payload.

merge_logic = """
                pending_payload = {
                    "worker_id": config["WORKER_ID"],
                    "goal_id": task.get("goal_id"),
                    "task_id": task["task_id"],
                    "dispatch_id": task.get("dispatch_id"),
                    "attempt_id": task.get("attempt_id"),
                    "run_id": result.get("run_id", str(uuid.uuid4())),
                    "result_id": str(uuid.uuid4()),
                    "status": result.get("status", "FAILED"),
                    "artifacts": artifact_evidence,
                    "provider": "windows_native",
                    "raw_result": result
                }
                
                # Merge revenue payload specifics if present
                if "artifact_content_base64" in result:
                    pending_payload["artifact_name"] = result["artifact_name"]
                    pending_payload["artifact_sha256"] = result["artifact_sha256"]
                    pending_payload["artifact_content_base64"] = result["artifact_content_base64"]
                    pending_payload["result_data"] = result.get("result_data", {})
"""

content = content.replace(
    '''                pending_payload = {
                    "worker_id": config["WORKER_ID"],
                    "goal_id": task.get("goal_id"),
                    "task_id": task["task_id"],
                    "dispatch_id": task.get("dispatch_id"),
                    "attempt_id": task.get("attempt_id"),
                    "run_id": result.get("run_id", str(uuid.uuid4())),
                    "result_id": str(uuid.uuid4()),
                    "status": result.get("status", "FAILED"),
                    "artifacts": artifact_evidence,
                    "provider": "windows_native",
                    "raw_result": result
                }''',
    merge_logic
)

with open(filepath, "w") as f:
    f.write(content)
