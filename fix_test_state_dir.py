import sys

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

c = c.replace(
    'checkpoint_file = REPO_ROOT / "scripts" / "mac_worker" / "state" / "current_task.json"',
    'checkpoint_file = REPO_ROOT / "scripts" / "mac_worker" / "state_2" / "current_task.json"'
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

