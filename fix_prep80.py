import re

with open("scripts/execute_mac_prep80_suite.py", "r") as f:
    content = f.read()

parts = content.split('def execute_all():')
if len(parts) == 1:
    # Not needed, already has execute_all maybe? Let's check
    pass
else:
    # Wait, execute_mac_prep80_suite.py already has def execute_all() in it! Let's check it.
    print("Already has execute_all")
