import sys

content = open("scripts/courier_continue.py").read()

new_logic = """
        # We need to enforce sequential execution within each chain (e.g. PUBLIC DEPLOYMENT)
        # while allowing unrelated chains to execute concurrently.
        # Group tasks by their base name (the part before ' - ')
        chain_unproven_seen = {}
        
        safe_executable_tasks = []
        blocked_tasks_this_run = set()
        
        for t in tasks:
            base_name = t["edge_name"].split(" - ")[0]
            
            is_runnable = False
            if not chain_unproven_seen.get(base_name, False):
                is_runnable = True
                chain_unproven_seen[base_name] = True
            
            if not is_runnable:
                continue
"""

# We need to replace the `first_unproven_seen` logic.
import re
content = re.sub(r'        first_unproven_seen = False.*?if not is_runnable:\n                continue', new_logic.strip(), content, flags=re.DOTALL)

open("scripts/courier_continue.py", "w").write(content)
