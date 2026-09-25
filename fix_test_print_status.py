import sys, re

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

replacement = """
        start_wait = time.time()
        last_status = None
        while time.time() - start_wait < 30:
            tasks = get_goal_tasks(seq_goal_id)
            t1 = [t for t in tasks if t["task_id"] == task_seq1]
            if t1:
                last_status = t1[0]["status"]
                if t1[0]["status"] == "DISPATCHED":
                    claimed = True
                    task1_data = t1[0]
                    break
            time.sleep(0.2)
            
        assert claimed, f"Task 1 was not claimed within timeout. Last status: {last_status}"
"""

c = re.sub(
    r'        start_wait = time\.time\(\)\n        while time\.time\(\) - start_wait < 30:\n            tasks = get_goal_tasks\(seq_goal_id\)\n            t1 = \[t for t in tasks if t\["task_id"\] == task_seq1\]\n            if t1 and t1\[0\]\["status"\] == "DISPATCHED":\n                claimed = True\n                task1_data = t1\[0\]\n                break\n            time\.sleep\(0\.2\)\n    \n        assert claimed, "Task 1 was not claimed within timeout"',
    replacement.strip(),
    c,
    flags=re.DOTALL
)

# And fix config_path NameError!
c = c.replace(
    "if config_path.exists() and 'orig_config' in locals():",
    "pass # if config_path.exists() and 'orig_config' in locals():"
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

