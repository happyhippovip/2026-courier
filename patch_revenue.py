import os
with open("scripts/revenue_customer_intake.py", "r") as f:
    c = f.read()

c = c.replace('"description":', '"goal_text":')
c = c.replace('"tasks":', '"workflow_plan":')

with open("scripts/revenue_customer_intake.py", "w") as f:
    f.write(c)
