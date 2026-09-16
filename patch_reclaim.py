import re

with open("server/app.py", "r") as f:
    c = f.read()

c = c.replace("""                    step["status"] = "HUMAN_REQUIRED"
                    step["recovery_reason"] = "STALE_WORKER_EFFECT_AMBIGUOUS"
                    quarantined_count += 1""", """                    step["status"] = "QUEUED"
                    step["worker_id"] = None
                    step["attempts"] = step.get("attempts", 0) + 1
                    quarantined_count += 1""")

# Also in the task map
c = c.replace("""                    if task:
                        task["status"] = "HUMAN_REQUIRED"
                        task["recovery_reason"] = "STALE_WORKER_EFFECT_AMBIGUOUS\"""", """                    if task:
                        task["status"] = "QUEUED"
                        task["worker_id"] = None
                        task["attempts"] = task.get("attempts", 0) + 1""")

with open("server/app.py", "w") as f:
    f.write(c)
