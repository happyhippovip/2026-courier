from scripts.courier_founder_mode import MultiChatGoalIntake
intake = MultiChatGoalIntake('.')
goal = intake.pop_next_goal()
print("POPPED:", goal)
