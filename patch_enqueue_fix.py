import sys

with open("scripts/run_live_production_goal.py", "r") as f:
    code = f.read()

old_opp = """                                opp = Opportunity(
                                    opportunity_id=task_id_new,
                                    source="MAC_CHIEF",
                                    project="Courier",
                                    description=summary,
                                    priority=5,
                                    risk="LOW",
                                    target_agent="CODEX",
                                    allowed_actions=["implement_bounded_improvement"],
                                    allowed_scope=["GLOBAL"]
                                )"""

new_opp = """                                opp = Opportunity(
                                    opportunity_id=task_id_new,
                                    source="MAC_CHIEF",
                                    project="Courier",
                                    objective_id="OBJ-EVAL",
                                    description=summary,
                                    priority=5,
                                    risk="LOW",
                                    target_agent="CODEX",
                                    allowed_actions=["implement_bounded_improvement"],
                                    allowed_scope=["GLOBAL"]
                                )"""

code = code.replace(old_opp, new_opp)

with open("scripts/run_live_production_goal.py", "w") as f:
    f.write(code)
