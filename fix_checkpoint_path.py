import re

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

# Fix checkpoint path logic
fix = """
    if launchd_wid == "MAC-WORKER-2":
        checkpoint_file = REPO_ROOT / "scripts" / "mac_worker" / "state_2" / "current_task.json"
    else:
        checkpoint_file = REPO_ROOT / "scripts" / "mac_worker" / "state" / "current_task.json"
        
    cleanup_file("scripts/mac_worker/state/current_task.json")
    cleanup_file("scripts/mac_worker/state_2/current_task.json")
"""

c = re.sub(
    r'    checkpoint_file = REPO_ROOT / "scripts" / "mac_worker" / "state" / "current_task\.json"',
    fix.strip('\n'),
    c,
    flags=re.DOTALL
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

