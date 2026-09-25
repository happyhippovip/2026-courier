import sys, re

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

replacement = """
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

c = c.replace(
    '    # Setup mac_worker_2 to hit 8081 via plist\n    import json\n    import subprocess\n    import os\n    \n    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.courier.mac_worker_2.plist")\n    with open(plist_path, "r") as f:\n        plist_content = f.read()\n        \n    new_plist_content = plist_content.replace("<string>http://127.0.0.1:8080/</string>", "<string>http://127.0.0.1:8081/</string>")\n    with open(plist_path, "w") as f:\n        f.write(new_plist_content)\n        \n    subprocess.run(["launchctl", "unload", plist_path])\n    subprocess.run(["launchctl", "load", plist_path])\n    subprocess.run(["launchctl", "start", "com.courier.mac_worker_2"])\n    \n    server_proc = subprocess.Popen([python_exe, "-m", "server.app"], env=env, cwd=str(REPO_ROOT))',
    replacement.strip()
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

