from scripts.courier_founder_mode import MultiChatGoalIntake, FounderModePlanner
intake = MultiChatGoalIntake('.')
planner = FounderModePlanner('.')
goal = {'goal': 'Continue building the existing social_platform from the current verified checkpoint. Inspect the real repository and select the highest-value missing coherent end-to-end user workflow or cross-feature consistency gap. Implement and verify substantial product improvements through Courier only. Continue across multiple meaningful increments until a coherent milestone is satisfied, a genuine human gate is reached, or a concrete unresolved blocker remains.', 'goal_id': 'd3c1c638-82dd-4461-a49a-89ce32b18979'}
next_missions = planner.discover_and_plan(goal, [])
print("NEXT MISSIONS:", next_missions)
