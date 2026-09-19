with open("scripts/courier_continue.py", "r") as f:
    code = f.read()

# 1. Add completed_this_session before the while True loop
code = code.replace(
    "    running_tasks = {} # mapping task edge_name to future\n    task_start_times = {} # mapping task edge_name to start time\n    while True:",
    "    running_tasks = {} # mapping task edge_name to future\n    task_start_times = {} # mapping task edge_name to start time\n    completed_this_session = set()\n    while True:"
)

# 2. Add finished tasks to completed_this_session
code = code.replace(
    "done_edges.append(edge_name)",
    "done_edges.append(edge_name)\n                completed_this_session.add(edge_name)"
)

# 3. Skip tasks in completed_this_session
code = code.replace(
    '            if t["edge_name"] in blocked_tasks_this_run:',
    '            if t["edge_name"] in completed_this_session:\n                continue\n            if t["edge_name"] in blocked_tasks_this_run:'
)

with open("scripts/courier_continue.py", "w") as f:
    f.write(code)
