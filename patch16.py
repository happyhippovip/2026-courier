with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

content = content.replace('"capability_request": "local repo analysis",\n                    "acceptance_criteria": self._extract_acceptance_criteria(goal_text)', '"capability_request": "local repo analysis"')

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
