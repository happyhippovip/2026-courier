from pathlib import Path

adapters_path = Path("scripts/courier_real_worker_adapters.py")
code = adapters_path.read_text()

replacement = """        payload_task = {
            "TASK_ID": task_id,
            "CREATED_AT": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "SOURCE": "MAC_ANTIGRAVITY",
            "TARGET_HOST": "DESKTOP-JDPRUGR",
            "PROJECT_PATH": r"C:\Dev\Windows-AI-OS",
            "WORKER": "WINDOWS",
            "SCOPE": scope_str,
            "ACTION": action_name,
            "STATUS": "PENDING",
            "SCRIPT": payload_in.get("prompt") or payload_in.get("action") or "",
            "payload": payload_in
        }"""

code = code.replace("""        payload_task = {
            "TASK_ID": task_id,
            "CREATED_AT": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "SOURCE": "MAC_ANTIGRAVITY",
            "TARGET_HOST": "DESKTOP-JDPRUGR",
            "PROJECT_PATH": r"C:\\Dev\\Windows-AI-OS",
            "WORKER": "WINDOWS",
            "SCOPE": scope_str,
            "ACTION": action_name,
            "STATUS": "PENDING"
        }""", replacement)

adapters_path.write_text(code)
print("Updated payload_task to include SCRIPT and payload")
