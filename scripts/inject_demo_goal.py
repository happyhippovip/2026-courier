import os
import sys
from scripts.courier_founder_mode import MultiChatGoalIntake

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/inject_demo_goal.py <goal_text>")
        sys.exit(1)
    
    workspace = os.getcwd()
    intake = MultiChatGoalIntake(workspace)
    goal_text = " ".join(sys.argv[1:])
    
    # Optional constraints
    constraints = ["Must be exactly 4 lines."]
    
    goal_id = intake.submit_goal("CLI", goal_text, priority=10, constraints=constraints)
    print(f"Demo goal injected successfully! Goal ID: {goal_id}")

if __name__ == "__main__":
    main()
