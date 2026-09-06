with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

content = content.replace('"normalized_task": "Analyze repo state to identify improvements.",\n                "capability_required": "local repo analysis",\n                "preferred_agent": "GEMINI"', '"normalized_task": "Analyze repo state to identify improvements.",\n                "capability_required": "local repo analysis",\n                "preferred_agent": "CLI1"')
content = content.replace('"requires_write": True,\n                "is_heavy": True,\n                "task": {\n                    "action": "discover_improvement_opportunities",', '"requires_write": False,\n                "is_heavy": True,\n                "task": {\n                    "action": "discover_improvement_opportunities",')

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
