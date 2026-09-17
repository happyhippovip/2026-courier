import json
with open('server/state/central_state.json', 'r') as f:
  data = json.load(f)
for k, v in data.get('tasks', {}).items():
  if 'TASK-WIN-TEST2' in k:
    print(f'{k}: {v.get("status")}')
