import sys
content = open("scripts/courier_continue.py").read()

# Just put a time.sleep(10) at the very end of the while True loop.
new_logic = """
                if task["edge_name"] not in bundle["record"].get("PROVEN_EDGES", []):
                    blocked_tasks_this_run.add(task["edge_name"])
                print(f"CHECKPOINT WRITTEN for {task['edge_name']}")
        
        import time
        time.sleep(10)
"""
import re
content = re.sub(r'                if task\["edge_name"\].*?print\(f"CHECKPOINT WRITTEN for \{task\[\'edge_name\'\]\}"\)', new_logic.strip(), content, flags=re.DOTALL)

open("scripts/courier_continue.py", "w").write(content)
