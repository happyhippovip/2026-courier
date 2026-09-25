import re

with open("server/app.py", "r") as f:
    lines = f.readlines()

new_logic = """
    # SECURITY HYGIENE: Reject unauthorized libraries or core security changes
    diff_text = str(task.get("result", {}).get("diff", "")) + str(data.get("diff", ""))
    
    has_requests = False
    import re as _re
    if _re.search(r'\\bimport requests\\b|\\bfrom requests\\b', diff_text) or "requests." in diff_text:
        has_requests = True
        
    if has_requests:
        task["blocker"] = "SECURITY_REJECTION: unzulässige Bibliothek requests"
        set_task_status(task, "BLOCKED")
        save_state(state)
        return jsonify({"approved": False, "blocker": task["blocker"]}), 200

    if "core-security" in diff_text.lower() or "motor-eligibility" in diff_text.lower() or "kern-sicherheitsregeln" in diff_text.lower():
        task["blocker"] = "SECURITY_REJECTION: Kern-Sicherheitsregeln geändert"
        set_task_status(task, "BLOCKED")
        save_state(state)
        return jsonify({"approved": False, "blocker": task["blocker"]}), 200
"""

in_approve_merge = False
out_lines = []
for line in lines:
    if "def approve_merge(task_id):" in line:
        in_approve_merge = True
    if in_approve_merge and 'set_task_status(task, "RECONCILED")' in line:
        out_lines.append(new_logic.strip("\n") + "\n")
        out_lines.append(line)
        in_approve_merge = False
    else:
        out_lines.append(line)

with open("server/app.py", "w") as f:
    f.writelines(out_lines)

