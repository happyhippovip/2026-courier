with open("scripts/courier_real_worker_adapters.py", "r") as f:
    code = f.read()

windows_adapter = """
def create_real_windows_adapter(root):
    def windows_worker(task_id: str, prompt: str, requires_write: bool, **kwargs):
        import subprocess
        import json
        from pathlib import Path
        import time

        task_hash = kwargs.get("task_hash", "winhash")
        mission_id = kwargs.get("mission_id", task_id)
        correlation_id = kwargs.get("correlation_id", "")
        worker_id = kwargs.get("worker_id", "WINDOWS")
        target_agent = kwargs.get("target_agent", "WINDOWS")
        
        payload_task = {
            "TASK_ID": task_id,
            "CREATED_AT": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "SOURCE": "MAC_ANTIGRAVITY",
            "TARGET_HOST": "DESKTOP-JDPRUGR",
            "PROJECT_PATH": r"C:\Dev\Windows-AI-OS",
            "WORKER": "WINDOWS",
            "SCOPE": "REMOTE_QUEUE_PROOF",
            "ACTION": "HEALTH_CHECK",
            "STATUS": "PENDING"
        }
        
        tmp_file = Path(f"/tmp/{task_id}_dispatch.json")
        with open(tmp_file, "w") as f:
            json.dump(payload_task, f)
            
        # Call mac_windows_dispatcher
        dispatcher_path = Path(root) / "scripts" / "mac_windows_dispatcher.py"
        res = subprocess.run(["python3", str(dispatcher_path), str(tmp_file)], capture_output=True, text=True)
        print(f"Windows dispatcher output:\\n{res.stdout}\\n{res.stderr}")
        
        success = False
        if "SUCCESS: Result fetched successfully." in res.stdout and "EXIT_CODE: 0" in res.stdout:
            success = True
            
        payload_out = {
            "worker_agent": "WINDOWS",
            "worker_type": "NATIVE_WINDOWS",
            "real_model_call": False,
            "separate_process": True,
            "target_agent": "WINDOWS",
            "task_id": task_id,
            "mission_id": mission_id,
            "task_hash": task_hash,
            "status": "COMPLETED" if success else "FAILED",
            "verdict": "PASS" if success else "FAIL",
            "summary": f"Windows health check execution. output: {res.stdout.strip()}",
            "zero_cost_policy": "ZERO_COST_ONLY",
            "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
            "action": "HEALTH_CHECK"
        }
        
        from scripts.courier_worker_adapters import canonical_hash
        return {
            "ack": {
                "schema_version": "1.0",
                "type": "ACK",
                "status": "ACCEPTED",
                "ack_mode": "SYNCHRONOUS_COMPLETION_VALIDATED",
                "task_hash": task_hash,
                "worker_id": worker_id,
                "target_agent": target_agent,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
            },
            "result": {
                "schema_version": "1.0",
                "type": "RESULT",
                "status": "COMPLETED" if success else "FAILED",
                "task_hash": task_hash,
                "worker_id": worker_id,
                "target_agent": target_agent,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
                "payload": payload_out,
                "result_fingerprint": canonical_hash(payload_out),
            }
        }
    return windows_worker
"""

code += windows_adapter
code = code.replace('"CLI1": create_real_cli1_adapter(root),', '"CLI1": create_real_cli1_adapter(root),\n        "WINDOWS": create_real_windows_adapter(root),')

with open("scripts/courier_real_worker_adapters.py", "w") as f:
    f.write(code)
