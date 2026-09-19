import re
import json

with open("server/app.py", "r") as f:
    content = f.read()

old_is_identical = '''            is_identical = (
                task.get("result", {}).get("result_id") == data.get("result_id") and
                task.get("result", {}).get("worker_id") == data.get("worker_id")
            )'''

new_is_identical = '''            # check canonical payload equality
            existing_result = task.get("result", {})
            # we need to compare relevant fields to ensure it's not contradictory
            is_identical = (
                existing_result.get("result_id") == data.get("result_id") and
                existing_result.get("worker_id") == data.get("worker_id") and
                existing_result.get("status") == data.get("status") and
                existing_result.get("artifacts") == data.get("artifacts")
            )'''

content = content.replace(old_is_identical, new_is_identical)

with open("server/app.py", "w") as f:
    f.write(content)
