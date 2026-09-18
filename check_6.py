import json
with open('server/state/central_state.json', 'r') as f:
    state = json.load(f)
print(state['tasks']['task-p12-6-v2']['status'])
