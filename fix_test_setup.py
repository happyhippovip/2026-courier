import sys, re

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

replacement = """
    # Setup mac_worker_2 to hit 8081
    import json
    import subprocess
    config2_path = REPO_ROOT / "scripts" / "mac_worker" / "config_2.json"
    orig_config2 = {}
    if config2_path.exists():
        with open(config2_path, "r") as f:
            orig_config2 = json.load(f)
            
    with open(config2_path, "w") as f:
        json.dump({"COURIER_SERVER": "http://127.0.0.1:8081", "WORKER_ID": "MAC-WORKER-2"}, f)
        
    # Stop and start mac_worker_2
    subprocess.run(["launchctl", "stop", "com.courier.mac_worker_2"])
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
    if config2_path.exists():
        with open(config2_path, "w") as f:
            json.dump(orig_config2, f)
    subprocess.run(["launchctl", "stop", "com.courier.mac_worker_2"])
    subprocess.run(["launchctl", "start", "com.courier.mac_worker_2"])
"""

c = re.sub(
    r'    if config_path\.exists.*?pass',
    teardown.strip(),
    c,
    flags=re.DOTALL
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

