with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

content = content.replace(
    '        expected_agent = task.get("preferred_agent") or dispatched_route\n        if expected_agent and res_data.get("target_agent") and res_data.get("target_agent") != expected_agent: return False',
    '        expected_agent = dispatched_route or task.get("preferred_agent")\n        if expected_agent and res_data.get("target_agent") != expected_agent: return False'
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(content)
