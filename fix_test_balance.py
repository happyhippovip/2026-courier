from pathlib import Path
import re

p = Path("tests/test_cannon_result_first.py")
content = p.read_text()

# Modify the submit function in the test to send estimated_cost: 0.0
target = 'resp = http.post("/goals", headers=auth(), json={"goal_text": "test", "workflow_plan": tasks})'
repl = 'resp = http.post("/goals", headers=auth(), json={"goal_text": "test", "workflow_plan": tasks, "estimated_cost": 0.0})'

if target in content:
    content = content.replace(target, repl)
    p.write_text(content)
    print("SUCCESS")
else:
    print("WARNING: target not found")
