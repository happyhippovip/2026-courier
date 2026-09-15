from pathlib import Path
from scripts.courier_goal_satisfaction_engine import GoalSatisfactionEngine

engine = GoalSatisfactionEngine(workspace_dir=Path("/Users/user/Downloads/2026-courier"))
state = engine.evaluate_system_satisfaction()

mac_executable_gaps = 0
for goal_id, goal_state in state.items():
    print(f"Goal {goal_id}: {goal_state.satisfaction_state}")
    if goal_state.satisfaction_state == "CONTINUE_SAFE_WORK":
        mac_executable_gaps += 1

print(f"Executable gaps: {mac_executable_gaps}")
