import sys, os, subprocess
plist_path = os.path.expanduser("~/Library/LaunchAgents/com.courier.mac_worker.plist")
with open(plist_path, "r") as f:
    c = f.read()

c = c.replace("/Users/user/Downloads/2026-courier/venv/bin/python", sys.executable)
with open(plist_path, "w") as f:
    f.write(c)

subprocess.run(["launchctl", "unload", plist_path])
subprocess.run(["launchctl", "load", plist_path])
subprocess.run(["launchctl", "start", "com.courier.mac_worker"])
