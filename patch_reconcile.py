with open("scripts/work_queue.py", "r") as f:
    text = f.read()

old_code = """                if "result" not in task:  # never completed: safe, no effect yet
                    task["status"] = "READY"
                    task.pop("owner", None)
                    reclaimed.append(tid)"""

new_code = """                if "result" not in task:  # may have crashed during execution
                    # STALE_WORKER_EFFECT_AMBIGUOUS: Replaying it risks a duplicate effect
                    task["status"] = "BLOCKED"
                    task["block_reason"] = "STALE_WORKER_EFFECT_AMBIGUOUS"
                    task.pop("owner", None)
                    reclaimed.append(tid)"""

text = text.replace(old_code, new_code)
text = text.replace("# Restart recovery: stale CLAIMED/RUNNING leases return to READY.", "# Restart recovery: stale CLAIMED/RUNNING leases are BLOCKED to prevent duplicate effects.")

with open("scripts/work_queue.py", "w") as f:
    f.write(text)
