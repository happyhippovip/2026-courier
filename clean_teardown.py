import sys

with open("tests/test_tomato_two_torture.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False

for line in lines:
    if line.strip() == 'try:':
        if len(new_lines) > 0 and 'def teardown_server' in new_lines[-1] or (len(new_lines) > 2 and 'def teardown_server' in new_lines[-3]):
            pass # wait, let's just find the exact block
            
    if 'subprocess.check_call(["launchctl", "stop", "com.courier.mac_worker"])' in line:
        new_lines.append('        for svc in ["com.courier.mac_worker", "com.courier.mac_worker_2"]:\n')
        new_lines.append('            subprocess.run(["launchctl", "stop", svc])\n')
        new_lines.append('        import time\n')
        new_lines.append('        time.sleep(1)\n')
        new_lines.append('        for svc in ["com.courier.mac_worker", "com.courier.mac_worker_2"]:\n')
        new_lines.append('            subprocess.run(["launchctl", "start", svc])\n')
        skip = True
        continue
        
    if skip:
        if line.strip() == 'pass' or line.strip() == 'print("Failed to restart launchd worker:", e)':
            skip = False
        continue

    new_lines.append(line)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.writelines(new_lines)
