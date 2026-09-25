import re
with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

replacement = """
    config_path = REPO_ROOT / "scripts/mac_worker/config.json"
    config_path_2 = REPO_ROOT / "scripts/mac_worker/config_2.json"
    
    with open(config_path, "w") as f:
        json.dump({"COURIER_SERVER": "http://127.0.0.1:8081"}, f)
    with open(config_path_2, "w") as f:
        json.dump({"COURIER_SERVER": "http://127.0.0.1:8081"}, f)
        
    for svc in ["com.courier.mac_worker", "com.courier.mac_worker_2"]:
        try:
            subprocess.check_call(["launchctl", "stop", svc])
            time.sleep(1)
            subprocess.check_call(["launchctl", "start", svc])
        except Exception:
            pass
"""

# replace the setup
c = re.sub(
    r'    config_path = REPO_ROOT / "scripts/mac_worker/config\.json".*?print\("Failed to restart launchd worker:", e\)',
    replacement.strip(),
    c,
    flags=re.DOTALL
)

# replace the teardown
teardown = """
    for svc in ["com.courier.mac_worker", "com.courier.mac_worker_2"]:
        try:
            subprocess.check_call(["launchctl", "stop", svc])
            time.sleep(1)
            subprocess.check_call(["launchctl", "start", svc])
        except Exception:
            pass
"""
c = re.sub(
    r'    try:\n        subprocess\.check_call\(\["launchctl", "stop", "com\.courier\.mac_worker"\]\).*?pass',
    teardown.strip(),
    c,
    flags=re.DOTALL
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

