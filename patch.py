import os

def patch_integration():
    path = 'scripts/integration_contract.py'
    with open(path, 'r') as f:
        content = f.read()

    old = '''    if "result_data" in result:
        required.add("result_data")'''
    new = '''    if "result_data" in result:
        required.add("result_data")
    if "stderr" in result:
        required.add("stderr")'''
        
    if old in content and "stderr" not in content:
        content = content.replace(old, new)
        with open(path, 'w') as f:
            f.write(content)
        print("Patched integration_contract.py")

def patch_app():
    path = 'server/app.py'
    with open(path, 'r') as f:
        content = f.read()

    old = '''                if retry_state["execution"] < MAX_RETRIES["execution"] and "AMBIGUOUS_CRASH" not in failure_reason:'''
    new = '''                wall_match = next((w for w in ["MONEY_REQUIRED", "SAFETY_REQUIRED", "PERMISSION_REQUIRED", "HUMAN_REQUIRED"] if w in failure_reason), None)
                if wall_match:
                    set_task_status(task, "HUMAN_REQUIRED")
                    task["next_action"] = "HUMAN_REVIEW"
                    task["recovery_reason"] = wall_match
                    task["blocker"] = f"Worker reported wall: {wall_match}"
                elif retry_state["execution"] < MAX_RETRIES["execution"] and "AMBIGUOUS_CRASH" not in failure_reason:'''
                
    if old in content and "wall_match" not in content:
        content = content.replace(old, new)
        with open(path, 'w') as f:
            f.write(content)
        print("Patched server/app.py")

patch_integration()
patch_app()
