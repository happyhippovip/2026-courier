import os
import re

with open("scripts/mac_worker/daemon.py", "r") as f:
    c = f.read()

current_result_file = 'STATE_DIR / "current_result.json"'
if "current_result.json" not in c:
    c = c.replace('current_task_state_file = STATE_DIR / "current_task.json"', 'current_task_state_file = STATE_DIR / "current_task.json"\n    current_result_file = STATE_DIR / "current_result.json"')

# Instead of blindly replacing `time.sleep(2**retries)`, let's replace the whole result posting block.
# First find the block from "payload = {" to "task = None"
start_str = """                payload = {
                    "worker_id": config["WORKER_ID"],"""

end_str = """                task = None"""

start_idx = c.find(start_str)
end_idx = c.find(end_str) + len(end_str)

if start_idx != -1 and end_idx != -1:
    old_block = c[start_idx:end_idx]
    
    new_block = """                payload = {
                    "worker_id": config["WORKER_ID"],
                    "goal_id": task.get("goal_id"),
                    "task_id": task["task_id"],
                    "dispatch_id": task.get("dispatch_id"),
                    "attempt_id": task.get("attempt_id"),
                    "run_id": str(uuid.uuid4()),
                    "result_id": str(uuid.uuid4()),
                    "status": result.get("status", "FAILED"),
                    "artifacts": artifact_evidence,
                    "provider": "mac_" + result.get("execution_mode", "unknown").lower(),
                    "raw_result": result
                }
                
                # S08/S05: Save current_result before attempting network post
                temp_res = str(current_result_file) + ".tmp"
                with open(temp_res, 'w') as f:
                    json.dump({"task": task, "payload": payload}, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_res, current_result_file)
                
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
                
                if current_task_state_file.exists():
                    os.remove(current_task_state_file)
                    
                # Clear crash count
                tid = task.get("task_id")
                if tid in crash_counts:
                    del crash_counts[tid]
                    with open(str(task_crash_file) + ".tmp", "w") as f:
                        json.dump(crash_counts, f)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(str(task_crash_file) + ".tmp", task_crash_file)
                    
                task = None"""
                
    c = c[:start_idx] + new_block + c[end_idx:]

# Handle checking current_result_file at startup
startup_str = """        with open(current_task_state_file, 'r') as f:
            task = json.load(f)"""

startup_block = """
        if current_result_file.exists():
            with open(current_result_file, 'r') as f:
                saved = json.load(f)
            write_log("Recovered unsent durable result from disk.")
            
            # Post loop right here
            import random
            post_backoff = 2
            while True:
                res, err = http_post(config, "/tasks/result", saved["payload"])
                if err:
                    write_log(f"Result post failed: {err}. Retrying in {post_backoff}s...")
                    time.sleep(post_backoff + random.uniform(0, 2))
                    post_backoff = min(60, post_backoff * 2)
                else:
                    write_log(f"Result posted successfully: {res}")
                    break
                    
            os.remove(current_result_file)
            if current_task_state_file.exists():
                os.remove(current_task_state_file)
            task = None
        elif current_task_state_file.exists():
            with open(current_task_state_file, 'r') as f:
                task = json.load(f)
"""

c = c.replace("""        with open(current_task_state_file, 'r') as f:
            task = json.load(f)""", startup_block)

c = c.replace("""    if current_task_state_file.exists():\n""" + startup_str, """    if current_task_state_file.exists() or current_result_file.exists():\n""" + startup_block)

# Let's fix the syntax error in my heartbeat sleep block where I messed up indentation earlier:
c = c.replace("""            if err:
                write_log(f"Heartbeat failed: {err}")
                registered = False
    error_backoff = 2
                time.sleep(error_backoff + __import__("random").uniform(0, 2))
                    error_backoff = min(60, error_backoff * 2)
                    continue""", """            if err:
                write_log(f"Heartbeat failed: {err}")
                registered = False
                time.sleep(error_backoff + __import__("random").uniform(0, 2))
                error_backoff = min(60, error_backoff * 2)
                continue""")

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(c)

