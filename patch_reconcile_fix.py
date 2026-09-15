import re
with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

replacement = """
                elif classification == "SAFE_RESUME_PRE_EFFECT":
                    # Update recovery count
                    rc = mission.get("recovery_count", 0) + 1
                    self.mission_queue.transition(mission_id, "PENDING", claimed_by=None, recovery_count=rc)
"""

new_content = re.sub(
    r"                elif classification == \"SAFE_RESUME_PRE_EFFECT\":.*?self\.mission_queue\.transition\(mission_id, \"PENDING\", claimed_by=None\)",
    replacement.strip("\n"),
    content,
    flags=re.DOTALL
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(new_content)
