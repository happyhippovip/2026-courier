from pathlib import Path

app_file = Path("server/app.py")
content = app_file.read_text()

target_str = """
        if task.get("worker_id") == worker_id:
            if task.get("status") != "DISPATCHED":
"""

replacement_str = """
        if task.get("worker_id") != worker_id:
            return jsonify({"error": "WORKER_MISMATCH", "reason": f"Task owned by {task.get('worker_id')}"}), 403
            
        if task.get("worker_id") == worker_id:
            if task.get("status") != "DISPATCHED":
"""

if target_str in content:
    app_file.write_text(content.replace(target_str, replacement_str))
    print("Patched.")
else:
    print("Not found.")
