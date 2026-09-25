import re
from pathlib import Path

p = Path("tests/test_windows_runtime_torture.py")
content = p.read_text()

content = re.sub(
    r'(res = urllib\.request\.urlopen\(urllib\.request\.Request\(f"\{API_URL\}/goals", method="POST", data=json\.dumps\(payload\)\.encode\(\), headers=HEADERS\)\)\n\s*t_assert\(res\.status == 200, "Goal created"\))',
    r'\1\n                res_data = json.loads(res.read().decode())\n                goal_id = res_data["goal_id"]\n                task_id = "task-win-torture-01"\n                urllib.request.urlopen(urllib.request.Request(f"{API_URL}/workers/register", method="POST", data=json.dumps({"worker_id": "WINDOWS-TORTURE-01", "capabilities": ["windows_native"], "git_sha": "cbaf514a"}).encode(), headers=HEADERS))\n                claim_res = json.loads(urllib.request.urlopen(urllib.request.Request(f"{API_URL}/tasks/claim", method="POST", data=json.dumps({"worker_id": "WINDOWS-TORTURE-01"}).encode(), headers=HEADERS)).read().decode())\n                dispatch_id = claim_res["task"]["dispatch_id"]\n                execution_ref = claim_res["task"]["execution_ref"]',
    content
)

content = re.sub(r'("dispatch_id": )f"dispatch-\{uuid\.uuid4\(\)\.hex\}",\n\s*("execution_ref": )f"exec-\{uuid\.uuid4\(\)\.hex\}"', r'\1dispatch_id,\n                    \2execution_ref', content)

content = content.replace('"runtime_identity": "test_identity",', '"runtime_identity": "WINDOWS-TORTURE-01",')

# Also delete the old `goal_id = "goal-win-torture"`
content = content.replace('goal_id = "goal-win-torture"\n                task_id = "task-win-torture-01"\n', '')

p.write_text(content)
