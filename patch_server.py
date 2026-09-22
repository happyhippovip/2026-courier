import re
with open("server/app.py", "r") as f:
    content = f.read()

# 1. Update _worker_is_eligible
old_eligible = '''    if time.time() <= state.get("provider_locks", {}).get(lock_key, 0):
        return False'''
new_eligible = '''    if time.time() <= state.get("provider_locks", {}).get(lock_key, 0):
        if task.get("mode") != "NATIVE":
            return False'''

if old_eligible in content:
    content = content.replace(old_eligible, new_eligible)

# 2. Update claim_task
old_claim = '''    if time.time() <= state.get("provider_locks", {}).get(lock_key, 0):
        save_state(state)
        return jsonify({"task": None, "reason": "PROVIDER_QUOTA_LOCKED"})'''
new_claim = '''    # We removed the global PROVIDER_QUOTA_LOCKED return here to allow NATIVE tasks to bypass the lock'''

if old_claim in content:
    content = content.replace(old_claim, new_claim)

with open("server/app.py", "w") as f:
    f.write(content)
print("Patched server/app.py")
