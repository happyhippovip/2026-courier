from pathlib import Path
import re

p = Path("scripts/run_live_production_goal.py")
code = p.read_text()

# We need to replace the static "target_agent": "GEMINI" assignment
# with dynamic logic based on `output`.

target_logic = """
                        output_lower = output.lower()
                        if any(k in output_lower for k in ["mac", "local", "python", "script", "code"]):
                            derived_target = "CODEX"
                        elif any(k in output_lower for k in ["windows", "powershell", "remote"]):
                            derived_target = "WINDOWS"
                        else:
                            derived_target = "GEMINI"

                        from scripts.opportunity_queue import Opportunity
                        new_opp = Opportunity(
                            opportunity_id="plan-imp-" + hashlib.sha256(output.encode()).hexdigest()[:8],
                            source="COURIER_GOAL_PLANNER",
                            objective_id="OBJ-OVERNIGHT",
                            project="Courier",
                            description="Derived task: " + output[:200],
                            priority=5,
                            expected_value="Progress towards goal",
                            status="READY",
                            target_agent=derived_target,
                            allowed_actions=["implement_bounded_improvement"],
                            allowed_scope=["UNKNOWN_WRITE"]
                        )
"""

pattern = r"                        from scripts\.opportunity_queue import Opportunity\n                        new_opp = Opportunity\([\s\S]*?allowed_scope=\[\"UNKNOWN_WRITE\"\]\n                        \)"

if re.search(pattern, code):
    code = re.sub(pattern, target_logic.strip(), code)
    p.write_text(code)
    print("Patched target_agent logic.")
else:
    print("Pattern not found!")
