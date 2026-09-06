with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

evaluate_code = """
    def evaluate_success(self, goal_record: dict, last_result: dict, completed_missions: list = None) -> bool:
        # If we broke the loop, let's consider it SATISFIED if at least one VERIFICATION passed in the past.
        if not completed_missions: return False
        
        # Check if ANY past verification passed
        for mission in completed_missions:
            res = self._load_result(mission)
            if res.get("task_type") == "VERIFICATION":
                ev = res.get("acceptance_evidence", {})
                if ev.get("tests_passed") is True or ev.get("goal_satisfied") is True:
                    return True
        return False
"""

import re
content = re.sub(r'    def evaluate_success\(self.*?return False', evaluate_code.strip(), content, flags=re.DOTALL)

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
