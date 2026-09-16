import os
with open("scripts/mac_worker/daemon.py", "r") as f:
    c = f.read()

current_result_file = "STATE_DIR / 'current_result.json'"
if "current_result_file = STATE_DIR" not in c:
    c = c.replace('current_task_state_file = STATE_DIR / "current_task.json"', 'current_task_state_file = STATE_DIR / "current_task.json"\n    current_result_file = STATE_DIR / "current_result.json"')

# On startup, check for current_result.json
startup_check = """
        if current_result_file.exists():
            try:
                with open(current_result_file, 'r') as f:
                    import json
                    saved_result = json.load(f)
                write_log("Recovered unsent durable result from disk.")
                result_payload = saved_result.get("payload")
                task = saved_result.get("task")
                # Go directly to posting
            except Exception as e:
                write_log(f"Failed to read current_result_file: {e}")
"""

# In the loop, when formatting payload:
write_result_atomic = """
                temp_result = str(current_result_file) + ".tmp"
                with open(temp_result, 'w') as f:
                    import json
                    json.dump({"task": task, "payload": payload}, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_result, current_result_file)
"""

post_loop = """
                # Infinite backoff loop for posting result (S05: no lost tasks, low-load waiting)
                import random
                post_backoff = 2
                while True:
                    res, err = http_post(config, "/tasks/result", payload)
                    if err:
                        write_log(f"Result post failed: {err}. Retrying in {post_backoff}s...")
                        time.sleep(post_backoff + random.uniform(0, 2))
                        post_backoff = min(60, post_backoff * 2)
                    else:
                        write_log(f"Result posted successfully: {res}")
                        break
                        
                if current_result_file.exists():
                    os.remove(current_result_file)
"""

# Let's completely rewrite the main loop structure for clarity, or just apply replacements carefully.

