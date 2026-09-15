import os
import sys
from scripts.courier_founder_mode import MultiChatGoalIntake

intake = MultiChatGoalIntake(os.getcwd())
goal = " ".join(sys.argv[1:])
intake.submit_goal("brother_demo", goal)
print("Demo goal injected successfully.")
