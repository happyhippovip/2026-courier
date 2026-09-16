import os
with open("scripts/mac_worker/daemon.py", "r") as f:
    c = f.read()

# Add single instance lock (S01)
lock_code = """
import fcntl
def acquire_single_instance_lock():
    lock_file = STATE_DIR / "daemon.lock"
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        print("Another instance of daemon is already running. Exiting.")
        sys.exit(0)
"""

if "acquire_single_instance_lock" not in c:
    c = c.replace("def loop():", lock_code + "\ndef loop():\n    _lock_fd = acquire_single_instance_lock()\n")

# Add crash loop breaker (S02)
crash_breaker = """
    # S02 Crash loop breaker
    task_crash_file = STATE_DIR / "task_crash_count.json"
    crash_counts = {}
    if task_crash_file.exists():
        try:
            with open(task_crash_file, "r") as f:
                crash_counts = json.load(f)
        except:
            pass

    # Load previously claimed task for duplicate protection
    task = None
    if current_task_state_file.exists():
        write_log("Found unfinished task from previous run, resuming...")
        with open(current_task_state_file, 'r') as f:
            task = json.load(f)
            
        # Increment crash count
        tid = task.get("task_id", "unknown")
        c_count = crash_counts.get(tid, 0) + 1
        crash_counts[tid] = c_count
        with open(task_crash_file, "w") as f:
            json.dump(crash_counts, f)
            
        if c_count > 2:
            write_log(f"Task {tid} has crashed {c_count} times. Breaking circuit and returning FAILED.")
            # Post failed result
            payload = {
                "worker_id": config["WORKER_ID"],
                "goal_id": task.get("goal_id"),
                "task_id": tid,
                "status": "FAILED",
                "stderr": f"S02 Circuit Breaker: Task crashed {c_count} times.",
                "execution_mode": "CIRCUIT_BREAKER",
                "artifacts": [],
                "raw_result": {"status": "FAILED", "reason": "CRASH_LOOP"}
            }
            http_post(config, "/tasks/result", payload)
            if current_task_state_file.exists():
                os.remove(current_task_state_file)
            task = None
"""

c = c.replace("""
    # Load previously claimed task for duplicate protection
    task = None
    if current_task_state_file.exists():
        write_log("Found unfinished task from previous run, resuming...")
        with open(current_task_state_file, 'r') as f:
            task = json.load(f)
""", crash_breaker)

# Also clear crash count when a task finishes successfully or fails normally
clear_crash = """
                if current_task_state_file.exists():
                    os.remove(current_task_state_file)
                    
                # Clear crash count
                tid = task.get("task_id")
                if tid in crash_counts:
                    del crash_counts[tid]
                    with open(task_crash_file, "w") as f:
                        json.dump(crash_counts, f)
                    
                task = None
"""
c = c.replace("""
                if current_task_state_file.exists():
                    os.remove(current_task_state_file)
                    
                task = None
""", clear_crash)

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(c)

