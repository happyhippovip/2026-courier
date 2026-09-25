import sys

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

debug = """
    t_a_waiting = False
    for _ in range(25):
        tasks = get_goal_tasks(goal_a_id)
        if tasks and tasks[0]["status"] == "WAITING_PROVIDER":
            t_a_waiting = True
            break
        time.sleep(0.5)
        
    print(f"[DEBUG] WORKERS AFTER WAITING_PROVIDER: {http_get('/workers')}", flush=True)
"""
c = c.replace(
    '''    t_a_waiting = False
    for _ in range(25):
        tasks = get_goal_tasks(goal_a_id)
        if tasks and tasks[0]["status"] == "WAITING_PROVIDER":
            t_a_waiting = True
            break
        time.sleep(0.5)''',
    debug.strip()
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

