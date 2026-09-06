with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

old_block = """                self.intake.set_status(goal["goal_id"], "BLOCKED", blocker_evidence=evidence)
                break"""
new_block = """                if status == "FAILED":
                    continue
                self.intake.set_status(goal["goal_id"], "BLOCKED", blocker_evidence=evidence)
                break"""

content = content.replace(old_block, new_block)

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
