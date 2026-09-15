from pathlib import Path
import re

p = Path("scripts/run_live_production_goal.py")
code = p.read_text()

# Insert `last_derived_task_id = None` before `while True:`
code = code.replace("    while True:\n        mac_result_consumer.consume_results()", "    last_derived_task_id = None\n    while True:\n        mac_result_consumer.consume_results()")

# Replace the derived task addition block
old_block = """                        new_opp = Opportunity(
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
                        queue.add_opportunity(new_opp)
                        print(f"Added new derived task {new_opp.opportunity_id}")
                        continue"""

new_block = """                        new_opp = Opportunity(
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
                        
                        if last_derived_task_id == new_opp.opportunity_id:
                            print(f"Derived identical task {new_opp.opportunity_id} again. Sleeping 30s...")
                            time.sleep(30)
                        last_derived_task_id = new_opp.opportunity_id
                        
                        queue.add_opportunity(new_opp)
                        print(f"Added new derived task {new_opp.opportunity_id}")
                        continue"""

if old_block in code:
    code = code.replace(old_block, new_block)
    p.write_text(code)
    print("Patched spin loop successfully.")
else:
    print("Could not find old block.")

