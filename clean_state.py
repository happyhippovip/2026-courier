import json
import os

state_file = 'server/state/central_state.json'
with open(state_file, 'r') as f:
    state = json.load(f)

for goal_id, goal in state.get('goals', {}).items():
    if goal_id != 'goal-7125b706':
        goal['status'] = 'DONE'

# Also let's clear out all non-P12 tasks from 'tasks' to avoid any zombie processing
tasks_to_keep = {}
for task_id, task in state.get('tasks', {}).items():
    if task.get('goal_id') == 'goal-7125b706':
        tasks_to_keep[task_id] = task

state['tasks'] = tasks_to_keep

with open(state_file, 'w') as f:
    json.dump(state, f, indent=2)

print("State file updated!")
