import re
from pathlib import Path

adapters_path = Path("scripts/courier_real_worker_adapters.py")
code = adapters_path.read_text()

new_adapter = """def create_real_windows_adapter(root):
    def windows_worker(task_envelope: dict) -> dict:
        import subprocess
        import json
        from pathlib import Path
        import time

        task_hash = task_envelope.get("task_hash", "winhash")
        worker_id = task_envelope.get("worker_id", "WINDOWS")
        target_agent = task_envelope.get("target_agent", "WINDOWS")
        mission_id = task_envelope.get("mission_id", "")
        task_id = task_envelope.get("task_id", task_hash[:16])
        correlation_id = str(task_envelope.get("correlation_id", ""))
        
        payload_in = task_envelope.get("payload", {})
        action_name = payload_in.get("action") or task_envelope.get("action") or "UNKNOWN_ACTION"
        scope_in = payload_in.get("allowed_scope") or payload_in.get("scope") or task_envelope.get("scope") or task_envelope.get("allowed_scope") or []
        if isinstance(scope_in, list):
            scope_str = ",".join(scope_in)
        else:
            scope_str = str(scope_in)
            
        payload_task = {
            "TASK_ID": task_id,
            "CREATED_AT": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "SOURCE": "MAC_ANTIGRAVITY",
            "TARGET_HOST": "DESKTOP-JDPRUGR",
            "PROJECT_PATH": "C:\\\\Dev\\\\Windows-AI-OS",
            "WORKER": "WINDOWS",
            "SCOPE": scope_str,
            "ACTION": action_name,
            "STATUS": "PENDING"
        }
        
        tmp_file = Path(f"/tmp/{task_id}_dispatch.json")
        try:
            with open(tmp_file, "w") as f:
                json.dump(payload_task, f)
                
            dispatcher_path = Path(root).resolve() / "scripts" / "mac_windows_dispatcher.py"
            res = subprocess.run(["python3", str(dispatcher_path), str(tmp_file)], capture_output=True, text=True)
            
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
                "summary": f"Windows execution. stdout: {res.stdout.strip()}",
                "zero_cost_policy": "ZERO_COST_ONLY",
                "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
                "action": action_name
            }
            
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
                    "result_fingerprint": canonical_hash(payload_out) if "canonical_hash" in globals() else task_hash,
                }
            }
        finally:
            if tmp_file.exists():
                tmp_file.unlink()
    return windows_worker
"""

start_idx = code.find("def create_real_windows_adapter(root):")
end_idx = code.find("return windows_worker\n", start_idx) + len("return windows_worker\n")

if start_idx != -1 and end_idx != -1:
    code = code[:start_idx] + new_adapter + code[end_idx:]
    adapters_path.write_text(code)
    print("Patch windows adapter applied.")
else:
    print("Could not find adapter.")
