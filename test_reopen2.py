from scripts.courier_founder_mode import MultiChatGoalIntake
intake = MultiChatGoalIntake('.')
res = intake.reopen_invalidated_blocker("d3c1c638-82dd-4461-a49a-89ce32b18979")
print("REOPENED:", res)
