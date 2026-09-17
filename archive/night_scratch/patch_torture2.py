import sys, re
content = open("tests/test_tomato_two_torture.py").read()

content = content.replace(
'''checkpoint_file = REPO_ROOT / "scripts" / "mac_worker" / "state" / "current_task.json"''',
'''checkpoint_file = Path.home() / ".courier_runtime" / "scripts" / "mac_worker" / "state" / "current_task.json"''')

content = content.replace(
'''checkpoint_file = REPO_ROOT / "scripts" / "mac_worker" / "state" / "current_result.json"''',
'''checkpoint_file = Path.home() / ".courier_runtime" / "scripts" / "mac_worker" / "state" / "current_result.json"''')

open("tests/test_tomato_two_torture.py", "w").write(content)
