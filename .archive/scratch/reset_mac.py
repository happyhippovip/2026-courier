import json
with open('server/state/central_state.json', 'r') as f:
    state = json.load(f)
worker = state['workers']['MAC-MACBOOK-PRO-VON-USER-EDEA96']
print(f"Old task: {worker.get('current_task')}")
worker['current_task'] = None
worker['available'] = True
with open('server/state/central_state.json', 'w') as f:
    json.dump(state, f, indent=2)
print("Worker reset successfully.")
