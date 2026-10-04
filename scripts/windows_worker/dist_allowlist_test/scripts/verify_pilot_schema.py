import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.integration_contract import prepare_task, WORKER_IDS

with open('ops/ai/PILOT_DUMMY_TASK.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

assert data.get('goal_id'), 'goal_id required'
assert isinstance(data.get('workflow_plan'), list) and len(data['workflow_plan']) > 0, 'workflow_plan required'

for step in data['workflow_plan']:
    prepared = prepare_task(dict(step))
    assert prepared['task_id'] == step['task_id']
    assert prepared['attempt_id'] == f"{step['task_id']}:attempt:1"
    assert prepared['worker_id'] == WORKER_IDS[step['target_capability']]
    assert prepared['status'] == 'QUEUED'
    print(f"Task {prepared['task_id']} prepared successfully: worker={prepared['worker_id']}, status={prepared['status']}")

print('PILOT_DUMMY_SCHEMA_VERIFIED=PASS')
