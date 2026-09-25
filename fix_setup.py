import re

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

setup_replacement = """
    config_path = REPO_ROOT / "scripts/mac_worker/config.json"
    config_path_2 = REPO_ROOT / "scripts/mac_worker/config_2.json"
    
    import json
    with open(config_path, "w") as f:
        json.dump({"COURIER_SERVER": "http://127.0.0.1:8081", "WORKER_ID": "MAC-CLI-1"}, f)
    with open(config_path_2, "w") as f:
        json.dump({"COURIER_SERVER": "http://127.0.0.1:8081", "WORKER_ID": "MAC-WORKER-2"}, f)

    cleanup_file("scripts/mac_worker/state/current_task.json")
    cleanup_file("scripts/mac_worker/state_2/current_task.json")

    for svc in ["com.courier.mac_worker", "com.courier.mac_worker_2"]:
        subprocess.run(["launchctl", "stop", svc])
    import time
    time.sleep(1)
    for svc in ["com.courier.mac_worker", "com.courier.mac_worker_2"]:
        subprocess.run(["launchctl", "start", svc])
"""

c = re.sub(
    r'    config_path = REPO_ROOT / "scripts/mac_worker/config\.json".*?subprocess\.run\(\["launchctl", "start", svc\]\)',
    setup_replacement.strip('\n'),
    c,
    flags=re.DOTALL
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

