import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

target = """            if durable_result.get("status") == "SUCCESS":"""
repl = """            # P6: Sandbox Billing Deduction
            goal_id = task.get("goal_id")
            if goal_id and "goals" in state and goal_id in state["goals"]:
                actual_cost = float(data.get("actual_cost", 0.0))
                if actual_cost > 0:
                    import server.sandbox_billing as sandbox_billing
                    sandbox_billing.deduct_task_cost(state["goals"][goal_id], actual_cost)

            if durable_result.get("status") == "SUCCESS":"""

content = content.replace(target, repl)

p.write_text(content)
print("SUCCESS")
