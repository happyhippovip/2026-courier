import re
with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

replacement = """
                status = mission_result.get("status") if mission_result else "NO_PENDING_MISSION"
                
                if status == "VERIFIED_COMPLETE":
                    self.intake.mark_satisfied(goal["goal_id"])
                    break
                elif status in ("QUIESCENT_WAKEABLE", "WAIT_BRANCH_LOCAL_GATE"):
                    if running_or_verify:
                        print(f"Waiting for running/verifying missions... (status={status})")
                        time.sleep(5)
                        continue
                    break
                elif status == "CONTINUE_SAFE_WORK" or status == "DISCOVER_FROM_ACTIVE_ROOT_GOAL_GAPS":
                    # Let discover_and_plan generate new missions!
                    # Wait, if we break, discover_and_plan won't be called unless we loop again.
                    # But discover_and_plan is called at the TOP of the loop if `not pending`.
                    break
                elif status == "NO_PENDING_MISSION":
                    break
"""

new_content = re.sub(
    r"if not mission_result or mission_result\.get\(\"status\"\).*?\n\s*break # Queue somehow empty",
    replacement.strip(),
    content,
    flags=re.DOTALL
)

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(new_content)
