import re

with open("scripts/courier_continue.py", "r") as f:
    content = f.read()

content = content.replace("    if edge.startswith('HANG'):\n        import time\n        time.sleep(20)\n", "")

hang_code = '''    edge = task['edge_name']
    hang_edges = [
        "PUBLIC DEPLOYMENT - SAFE_AUTOMATABLE_PREPARATION",
        "PILOT INTAKE - SAFE_AUTOMATABLE_PREPARATION",
        "SALES PACKAGE - SAFE_AUTOMATABLE_PREPARATION",
        "FIRST PILOT - SAFE_AUTOMATABLE_PREPARATION",
        "PAYMENT ONLY WHEN ACTUALLY REQUIRED - SAFE_AUTOMATABLE_PREPARATION"
    ]
    if edge in hang_edges:
        import time
        time.sleep(20)
'''

content = content.replace("    edge = task['edge_name']", hang_code)

with open("scripts/courier_continue.py", "w") as f:
    f.write(content)
