import os
import json

with open("scripts/revenue_customer_intake.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if '"capabilities": ["revenue_safety_audit"],' in line:
        new_lines.append('                "target_agent": "revenue",\n')

with open("scripts/revenue_customer_intake.py", "w") as f:
    f.writelines(new_lines)
