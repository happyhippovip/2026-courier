import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

# Add check budget logic inside the goal loop:
target = """        if goal["status"] == "ACTIVE" and "workflow_plan" in goal:"""
repl = """        if goal["status"] == "ACTIVE" and "workflow_plan" in goal:
            # P6: Sandbox Billing Check
            import server.sandbox_billing as sandbox_billing
            budget_ok, budget_err = sandbox_billing.check_goal_budget(goal)
            if not budget_ok:
                goal["status"] = "BLOCKED"
                goal["blocker"] = budget_err
                save_state(state)
                return jsonify({"error": budget_err}), 402
"""

content = content.replace(target, repl)

p.write_text(content)
print("SUCCESS")
