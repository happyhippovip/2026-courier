with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

content = content.replace('"normalized_task": "Discover implementation path",\n                "capability_required": "local repo analysis",\n                "preferred_agent": "GEMINI"', '"normalized_task": "Discover implementation path",\n                "capability_required": "local repo analysis",\n                "preferred_agent": "CLI1"')
content = content.replace('"normalized_task": f"Verify implementation in {\', \'.join(files)}",\n                "capability_required": "repo verification",\n                "preferred_agent": "GEMINI",\n                "is_heavy": False,\n                "requires_write": True,', '"normalized_task": f"Verify implementation in {\', \'.join(files)}",\n                "capability_required": "repo verification",\n                "preferred_agent": "CLI1",\n                "is_heavy": False,\n                "requires_write": False,')

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
