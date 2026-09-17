import sys

content = open("scripts/courier_continue.py").read()

new_logic = """
        if not safe_executable_tasks:
            if tasks:
                print(f"WAITING: No safe, unowned, independent executable tasks exist.")
                print(f"Blockers: {first_blocker}")
            else:
                print("GLOBAL STOP: CLEAN_IDLE. All tasks completed.")
                try:
                    bundle = update_ledger(ledger_path, "CLEAN_IDLE_ACHIEVED", None, bundle)
                except Exception as e:
                    pass
            import time
            time.sleep(10)
            continue
"""

import re
content = re.sub(r'        if not safe_executable_tasks:\n            if tasks:.*?sys\.exit\(0\)', new_logic.strip(), content, flags=re.DOTALL)

open("scripts/courier_continue.py", "w").write(content)
