with open("scripts/courier_founder_mode.py", "r") as f:
    text = f.read()

old_block = '''                    if not has_live:
                        has_blocked = any(m.get("goal") == g["goal"] and m.get("status") == "BLOCKED" and m.get("result_reference") == "WORKER_UNAVAILABLE" for m in missions)
                        if has_blocked:
                            g["status"] = "BLOCKED"'''
new_block = '''                    if not has_live:
                        has_blocked = any(m.get("goal") == g["goal"] and m.get("status") == "BLOCKED" and m.get("result_reference") == "WORKER_UNAVAILABLE" for m in missions)
                        if has_blocked:
                            g["status"] = "BLOCKED"
                        else:
                            # Stale ACTIVE with no live or blocked missions means the orchestrator crashed.
                            # Reset to PENDING so it can be picked up again.
                            g["status"] = "PENDING"'''
text = text.replace(old_block, new_block)

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(text)
