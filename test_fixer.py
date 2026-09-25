import sys, re

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

setup_replacement = """
    # Setup mac_worker_2 to hit 8081 via plist
    import json
    import subprocess
    import os
    import shutil
    
    # clear test_state.json
    state_file = REPO_ROOT / "server" / "state" / "test_state.json"
    if state_file.exists():
        state_file.unlink()
        
    # clear current_task.json and current_result.json
    for wf in ["state", "state_2"]:
        for sf in ["current_task.json", "current_result.json", "current_provider_wait.json"]:
            sfp = REPO_ROOT / "scripts" / "mac_worker" / wf / sf
            if sfp.exists():
                sfp.unlink()
                
    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.courier.mac_worker_2.plist")
    with open(plist_path, "r") as f:
        plist_content = f.read()
        
    new_plist_content = plist_content.replace("<string>http://127.0.0.1:8080/</string>", "<string>http://127.0.0.1:8081/</string>")
    with open(plist_path, "w") as f:
        f.write(new_plist_content)
        
    subprocess.run(["launchctl", "unload", plist_path])
    subprocess.run(["launchctl", "load", plist_path])
    subprocess.run(["launchctl", "start", "com.courier.mac_worker_2"])
    
    server_proc = subprocess.Popen([python_exe, "-m", "server.app"], env=env, cwd=str(REPO_ROOT))
"""

c = re.sub(
    r'    # waitress is missing.*?server_proc = subprocess\.Popen\(\[python_exe, "-m", "server\.app"\], env=env, cwd=str\(REPO_ROOT\)\)',
    setup_replacement.strip(),
    c,
    flags=re.DOTALL
)

teardown = """
    pass
    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.courier.mac_worker_2.plist")
    if os.path.exists(plist_path):
        with open(plist_path, "r") as f:
            plist_content = f.read()
        new_plist_content = plist_content.replace("<string>http://127.0.0.1:8081/</string>", "<string>http://127.0.0.1:8080/</string>")
        with open(plist_path, "w") as f:
            f.write(new_plist_content)
        subprocess.run(["launchctl", "unload", plist_path])
        subprocess.run(["launchctl", "load", plist_path])
        subprocess.run(["launchctl", "start", "com.courier.mac_worker_2"])
"""

c = re.sub(
    r'    if config_path\.exists.*?pass\n\n\ndef test',
    teardown.strip() + '\n\n\ndef test',
    c,
    flags=re.DOTALL
)

# Also fix the assert for step 3
step3_replacement = """
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
    step3_replacement.strip(),
    c,
    flags=re.DOTALL
)

# And fix goal B assert
c = c.replace(
    'assert goal_b_done, "Goal B failed to complete while Goal A was in WAITING_PROVIDER"',
    'assert goal_b_done, f"Goal B failed to complete while Goal A was in WAITING_PROVIDER. Status={get_goal(goal_b_id)} Tasks={get_goal_tasks(goal_b_id)}"'
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)
