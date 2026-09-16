import os
with open("server/app.py", "r") as f:
    c = f.read()

route_logic = """
            if durable_result.get("status") == "SUCCESS":
                task["status"] = "RESULT_RECEIVED" # wait for independent /verify
            else:
                is_crash_loop = durable_result.get("raw_result", {}).get("reason") == "CRASH_LOOP"
                
                if is_crash_loop:
                    # Keep goal alive, route portable work to github
                    task["status"] = "QUEUED"
                    task["worker_id"] = None
                    if "github" in state.get("workers", {}).get("GITHUB-DISPATCHER", {}).get("capabilities", []):
                        task["target_agent"] = "github"
                        task["target_capability"] = "github"
                    elif "linux" in task.get("capabilities", []):
                        task["target_agent"] = "linux"
                        task["target_capability"] = "linux"
                    # Also mark the crashing worker as unavailable for a bit if we wanted, but routing away is enough
                elif task.get("attempts", 1) < 3:
                    task["status"] = "QUEUED" # Retry
                    task["worker_id"] = None
                else:
                    task["status"] = "FAILED_TERMINAL"
"""

c = c.replace("""
            if durable_result.get("status") == "SUCCESS":
                task["status"] = "RESULT_RECEIVED" # wait for independent /verify
            else:
                if task.get("attempts", 1) < 3:
                    task["status"] = "QUEUED" # Retry
                    task["worker_id"] = None
                else:
                    task["status"] = "FAILED_TERMINAL"
""", route_logic)

with open("server/app.py", "w") as f:
    f.write(c)

