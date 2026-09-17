import json
with open('server/state/central_state.json', 'r') as f:
    state = json.load(f)
if 'WINDOWS-TEST-WORKER' in state['workers']:
    state['workers']['WINDOWS-TEST-WORKER']['current_task'] = None
    state['workers']['WINDOWS-TEST-WORKER']['available'] = True
if 'task-p12-1-v2' in state['tasks']:
    state['tasks']['task-p12-1-v2']['status'] = 'QUEUED'
    state['tasks']['task-p12-1-v2']['worker_id'] = None
for goal in state.get('goals', {}).values():
    for task in goal.get('workflow_plan', []):
        if task['task_id'] == 'task-p12-1-v2':
            task['status'] = 'QUEUED'
with open('server/state/central_state.json', 'w') as f:
    json.dump(state, f, indent=2)
print('Reset task-p12-1-v2 completely')
