import re

with open("scripts/courier_real_worker_adapters.py", "r") as f:
    text = f.read()

bad = """                "correlation_id": correlation_id,
                "task_id": task_id,
                    "mission_id": mission_id,
            "mission_id": mission_id,
            "result": {"""

good = """                "correlation_id": correlation_id,
                "task_id": task_id,
                "mission_id": mission_id,
            },
            "result": {"""

new_text = text.replace(bad, good)
if new_text != text:
    with open("scripts/courier_real_worker_adapters.py", "w") as f:
        f.write(new_text)
        print("Fixed syntax")
else:
    print("Could not find bad dict 2")
