import sys

with open("tests/test_tomato_two_torture.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False

for line in lines:
    if line.startswith('    env["PORT"] = "8081"'):
        new_lines.append(line)
        new_lines.append('    env["COURIER_STATE_FILE"] = "server/state/test_state.json"\n')
        continue
        
    if line.strip() == 'config_path = REPO_ROOT / "scripts/mac_worker/config.json"':
        skip = True
        new_lines.append('    config_path = REPO_ROOT / "scripts/mac_worker/config.json"\n')
        new_lines.append('    config_path_2 = REPO_ROOT / "scripts/mac_worker/config_2.json"\n')
        new_lines.append('    import json\n')
        new_lines.append('    with open(config_path, "w") as f:\n')
        new_lines.append('        json.dump({"COURIER_SERVER": "http://127.0.0.1:8081", "WORKER_ID": "MAC-CLI-1"}, f)\n')
        new_lines.append('    with open(config_path_2, "w") as f:\n')
        new_lines.append('        json.dump({"COURIER_SERVER": "http://127.0.0.1:8081", "WORKER_ID": "MAC-WORKER-2"}, f)\n')
        new_lines.append('\n')
        new_lines.append('    for svc in ["com.courier.mac_worker", "com.courier.mac_worker_2"]:\n')
        new_lines.append('        subprocess.run(["launchctl", "stop", svc])\n')
        new_lines.append('    import time\n')
        new_lines.append('    time.sleep(1)\n')
        new_lines.append('    for svc in ["com.courier.mac_worker", "com.courier.mac_worker_2"]:\n')
        new_lines.append('        subprocess.run(["launchctl", "start", svc])\n')
        continue
        
    if skip:
        if line.strip().startswith('orig_keychain_srv'):
            skip = False
            new_lines.append(line)
        continue
        
    new_lines.append(line)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.writelines(new_lines)
