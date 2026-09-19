import re

with open("scripts/mac_worker/daemon.py", "r") as f:
    content = f.read()

# The payload dictionary is built around line 450 and 590
# Let's search for "dispatch_id": task.get("dispatch_id"),
payload_pattern = r'"dispatch_id": task\.get\("dispatch_id"\),'
replacement = r'"dispatch_id": task.get("dispatch_id"),\n                        "runtime_identity": task.get("server_binding"),'
new_content = re.sub(payload_pattern, replacement, content)

with open("scripts/mac_worker/daemon.py", "w") as f:
    f.write(new_content)

print("Patched daemon.py successfully")
