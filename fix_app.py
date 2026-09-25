with open("server/app.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'if time.time() <= state.get("provider_locks", {}).get(lock_key, 0):' in line:
        if 'return False' in lines[lines.index(line) + 1]:
            # _worker_is_eligible block
            new_lines.append(line)
            new_lines.append('        if task.get("mode") != "NATIVE":\n')
            new_lines.append('            return False\n')
            lines[lines.index(line) + 1] = '' # skip original return False
            continue
        
        elif 'save_state(state)' in lines[lines.index(line) + 1]:
            # claim_task block
            new_lines.append('    is_provider_locked = time.time() <= state.get("provider_locks", {}).get(lock_key, 0)\n')
            lines[lines.index(line) + 1] = '' # skip save_state
            lines[lines.index(line) + 2] = '' # skip return jsonify
            continue

    if 'return jsonify({"task": None, "reason": "NO_WORK_AVAILABLE"})' in line:
        new_lines.append('    if is_provider_locked:\n')
        new_lines.append('        return jsonify({"task": None, "reason": "PROVIDER_QUOTA_LOCKED"})\n')
        new_lines.append(line)
        continue

    new_lines.append(line)

with open("server/app.py", "w") as f:
    f.writelines(new_lines)
