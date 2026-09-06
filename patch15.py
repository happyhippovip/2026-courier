with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

content = content.replace('"normalized_task": "Analyze repo state to identify improvements.",\n                "capability_required": "local repo analysis",\n                "preferred_agent": "GEMINI"', '"normalized_task": "Analyze repo state to identify improvements.",\n                "capability_required": "local repo analysis",\n                "preferred_agent": "CLI1"')

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
