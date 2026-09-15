import sys
import re

with open('scripts/courier_real_worker_adapters.py', 'r') as f:
    code = f.read()

old_block = """        if processed_file.exists():
            try:
                codex_res = json.loads(processed_file.read_text())
                if codex_res.get("task_id") == task_id:
                    result_status = codex_res.get("status", "COMPLETED")
                    payload_out.update(codex_res)
                    payload_out["status"] = result_status
                    success = True
            except Exception as e:
                print(f"Error reading codex result: {e}")
                success = False"""

new_block = """        if processed_file.exists():
            try:
                codex_res = json.loads(processed_file.read_text())
                if codex_res.get("task_id") == task_id:
                    result_status = codex_res.get("status", "COMPLETED")
                    payload_out.update(codex_res)
                    payload_out["status"] = result_status
                    success = True
                    if codex_res.get("payload", {}).get("verdict") == "BLOCKED_RATE_LIMIT":
                        payload_out["status"] = "BLOCKED"
                        result_status = "BLOCKED"
                        success = False
            except Exception as e:
                print(f"Error reading codex result: {e}")
                success = False"""

code = code.replace(old_block, new_block)

with open('scripts/courier_real_worker_adapters.py', 'w') as f:
    f.write(code)
