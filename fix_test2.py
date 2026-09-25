import re

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

setup_replacement = """
    config_path = REPO_ROOT / "scripts/mac_worker/config.json"
    config_path_2 = REPO_ROOT / "scripts/mac_worker/config_2.json"
    
    import json
    with open(config_path, "w") as f:
        json.dump({"COURIER_SERVER": "http://127.0.0.1:8081", "WORKER_ID": "MAC-CLI-TEST"}, f)
    with open(config_path_2, "w") as f:
        json.dump({"COURIER_SERVER": "http://127.0.0.1:8081", "WORKER_ID": "MAC-WORKER-2"}, f)

    for svc in ["com.courier.mac_worker", "com.courier.mac_worker_2"]:
        print(f"Restarting {svc}...")
        subprocess.run(["launchctl", "stop", svc], capture_output=True)
        time.sleep(2)
        res = subprocess.run(["launchctl", "start", svc], capture_output=True)
        if res.returncode != 0:
            print(f"Failed to start {svc}: {res.stderr.decode()}")
"""

c = re.sub(
    r'    config_path = REPO_ROOT / "scripts/mac_worker/config\.json".*?pass',
    setup_replacement.strip('\n'),
    c,
    flags=re.DOTALL
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

