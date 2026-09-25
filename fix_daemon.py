from pathlib import Path
p = Path("scripts/windows_worker/daemon.py")
content = p.read_text()

content = content.replace('"runtime_identity": os.environ.get("COURIER_WORKER_ID") or config.get("WORKER_ID", "default-win-worker"),', '"runtime_identity": task.get("server_binding"),')
# Wait, for the crash one, it uses crashed_task
content = content.replace('                    "provider": "windows_native",\n            "runtime_identity": task.get("server_binding"),', '                    "provider": "windows_native",\n            "runtime_identity": crashed_task.get("server_binding"),')

p.write_text(content)
