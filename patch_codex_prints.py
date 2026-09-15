from pathlib import Path

adapters_path = Path("scripts/courier_real_worker_adapters.py")
code = adapters_path.read_text()

code = code.replace('print(f"Calling CODEX dispatcher for task_id: {task_id}")\n', '')
code = code.replace('print(f"Codex dispatcher output:\\n{res.stdout}\\n{res.stderr}")\n', '')

adapters_path.write_text(code)
print("Codex debug prints removed.")
