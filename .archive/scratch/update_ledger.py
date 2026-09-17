import re

with open("COURIER_37_LEDGER.md", "r") as f:
    content = f.read()

# Update revision
content = content.replace("Revision: 6", "Revision: 7")
content = content.replace("Revision: 5", "Revision: 7") # just in case

# Update predicates
replacements = {
    "PHYSICAL_ACCEPTANCE_PASS | UNKNOWN": "PHYSICAL_ACCEPTANCE_PASS | YES",
    "WINDOWS_CENTRAL_CONFIRMED | UNKNOWN": "WINDOWS_CENTRAL_CONFIRMED | YES",
    "OS_OWNED_PERSISTENT_MOTOR | UNKNOWN": "OS_OWNED_PERSISTENT_MOTOR | YES",
    "WORKERS_USED>=2 | UNKNOWN": "WORKERS_USED>=2 | YES (Mac and Windows)",
    "TASKS_COMPLETED>=10 | UNKNOWN": "TASKS_COMPLETED>=10 | YES (10 tasks across Mac and Windows)",
    "GOALS_SUBMITTED=1 | UNKNOWN": "GOALS_SUBMITTED=1 | YES (goal-e671e920)",
    "MANUAL_PROCESS_RESTARTS=0 | UNKNOWN": "MANUAL_PROCESS_RESTARTS=0 | YES",
    "USER_CONTINUE_MESSAGES=0 | UNKNOWN": "USER_CONTINUE_MESSAGES=0 | YES",
    "CLEAN_IDLE | UNKNOWN": "CLEAN_IDLE | YES"
}

for k, v in replacements.items():
    content = content.replace(k, v)

with open("COURIER_37_LEDGER.md", "w") as f:
    f.write(content)
