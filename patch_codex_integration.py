import re
from pathlib import Path

# 1. Update run_live_production_goal.py
run_live_path = Path("scripts/run_live_production_goal.py")
code = run_live_path.read_text()

# Remove the hardcoded CODEX bypass block
code = re.sub(
    r'\s+if worker_id == "CODEX":\s+import subprocess\s+print\(f"Routing kickstart to CODEX via router_dispatch_codex.py: \{task_id\}"\)\s+cmd = \[sys\.executable, str\(SCRIPTS_DIR / "router_dispatch_codex\.py"\), task_id, prompt_text\]\s+subprocess\.run\(cmd\)\s+kickstarted = True\s+continue\n',
    '\n',
    code,
    flags=re.MULTILINE
)
run_live_path.write_text(code)


# 2. Update courier_real_worker_adapters.py
adapters_path = Path("scripts/courier_real_worker_adapters.py")
adapters_code = adapters_path.read_text()

# Replace create_real_codex_adapter
new_adapter = """def create_real_codex_adapter(repo_root=None) -> Any:
    root = Path(repo_root or COURIER_REPO_ROOT).resolve()

    def codex_worker(task_envelope: Dict[str, Any]) -> Dict[str, Any]:
        import subprocess
        import json
        from pathlib import Path

        task_hash = task_envelope["task_hash"]
        worker_id = task_envelope["worker_id"]
        target_agent = task_envelope["target_agent"]
        mission_id = task_envelope.get("mission_id", "")
        task_id = task_envelope.get("task_id", task_hash[:16])
        payload_in = task_envelope.get("payload", {})
        correlation_id = str(task_envelope.get("correlation_id", ""))
        
        if target_agent != "CODEX":
            return {"status": "FAIL_CLOSED"}

        instruction = str(payload_in.get("prompt") or payload_in.get("action") or "Inspect and analyse the repository.")

        # Invoke router_dispatch_codex.py
        dispatch_script = root / "scripts" / "router_dispatch_codex.py"
        print(f"Calling CODEX dispatcher for task_id: {task_id}")
        res = subprocess.run(
            ["python3", str(dispatch_script), task_id, instruction],
            capture_output=True,
            text=True
        )
        print(f"Codex dispatcher output:\\n{res.stdout}\\n{res.stderr}")
        
        success = res.returncode == 0
        
        processed_file = root / "events" / "processed" / f"{task_id}-result.json"
        result_status = "FAILED"
        payload_out = {
            "worker_agent": "CODEX",
            "task_id": task_id,
            "mission_id": mission_id,
            "task_hash": task_hash,
            "target_agent": target_agent,
            "summary": res.stdout.strip(),
            "status": "FAILED",
        }
        
        if processed_file.exists():
            try:
                codex_res = json.loads(processed_file.read_text())
                if codex_res.get("task_id") == task_id:
                    result_status = codex_res.get("status", "COMPLETED")
                    payload_out.update(codex_res)
                    payload_out["status"] = result_status
                    success = True
            except Exception as e:
                print(f"Error reading codex result: {e}")
                success = False

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
                "status": result_status if success else "FAILED",
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
    return codex_worker
"""

adapters_code = re.sub(
    r"def create_real_codex_adapter.*?return codex_worker\n",
    new_adapter,
    adapters_code,
    flags=re.DOTALL
)

adapters_path.write_text(adapters_code)

print("Patch applied.")
