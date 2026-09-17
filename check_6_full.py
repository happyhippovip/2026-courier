import json
with open('server/state/central_state.json', 'r') as f:
    state = json.load(f)
print(json.dumps(state['tasks']['task-p12-6-v2'], indent=2))
