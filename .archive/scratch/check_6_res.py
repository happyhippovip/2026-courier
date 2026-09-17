import json
with open('server/state/central_state.json', 'r') as f:
    state = json.load(f)
res = state['tasks']['task-p12-6-v2']['result']
print(json.dumps(res, indent=2))
