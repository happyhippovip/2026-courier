import sys

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

c = c.replace(
    'assert goal_b_done, "Goal B failed to complete while Goal A was in WAITING_PROVIDER"',
    'assert goal_b_done, f"Goal B failed to complete while Goal A was in WAITING_PROVIDER. Status={get_goal(goal_b_id)} Tasks={get_goal_tasks(goal_b_id)}"'
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

