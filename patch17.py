with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

content = content.replace('"task": {\n                    "action": "implement_improvement",', '"task": {\n                    "action": "implement_improvement",\n                    "acceptance_criteria": self._extract_acceptance_criteria(goal_text),')

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
