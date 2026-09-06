import sys

with open("scripts/courier_founder_mode.py", "r") as f:
    lines = f.read().split("\n")

out = []
i = 0
while i < len(lines):
    line = lines[i]
    if "def __init__(self, workspace_dir: str):" in line and "class MultiChatGoalIntake:" in "\n".join(lines[max(0, i-5):i]):
        out.append(line)
        out.append("        pass")
    elif "def set_status(" in line:
        # Add reopen_invalidated_blocker before it
        out.append("    def reopen_invalidated_blocker(self, goal_id: str) -> bool:")
        out.append("        records = self._read_no_lock()")
        out.append("        for r in records:")
        out.append("            if r[\"goal_id\"] == goal_id and r[\"status\"] in (\"BLOCKED\", \"FAILED\", \"HUMAN_GATE\"):")
        out.append("                r[\"status\"] = \"PENDING\"")
        out.append("                self._write_no_lock(records)")
        out.append("                return True")
        out.append("        return False")
        out.append("")
        out.append(line)
    elif 'if status == "FAILED":' in line:
        i += 1 # skip continue
        continue
    elif 'self.intake.set_status(goal["goal_id"], "BLOCKED", blocker_evidence=evidence)' in line:
        out.append('                from scripts.courier_self_repair import CourierSelfRepair')
        out.append('                repair = CourierSelfRepair(self.workspace_dir)')
        out.append('                res = repair.handle_failure(')
        out.append('                    goal_id=goal["goal_id"],')
        out.append('                    original_goal=goal["goal"],')
        out.append('                    failure=mission_result.get("reason", "Unknown failure")')
        out.append('                )')
        out.append('                if res.get("status") == "REPAIR_QUEUED":')
        out.append('                    continue')
        out.append('                ')
        out.append(line)
    else:
        out.append(line)
    i += 1

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write("\n".join(out))
