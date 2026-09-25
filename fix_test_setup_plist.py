import sys, re

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

replacement = """
    # Setup mac_worker_2 to hit 8081 via plist
    import json
    import subprocess
    import os
    
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
    replacement.strip(),
    c,
    flags=re.DOTALL
)

teardown = """
    if config_path.exists() and 'orig_config' in locals():
        with open(config_path, "w") as cf:
            json.dump(orig_config, cf)
            
    plist_path = os.path.expanduser("~/Library/LaunchAgents/com.courier.mac_worker_2.plist")
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

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

