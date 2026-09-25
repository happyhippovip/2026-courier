import re
import hashlib
import json

with open("scripts/cannon_motor.py", "r") as f:
    content = f.read()

# For line 389:
replacement_389 = """                import hashlib
                _payload_str = json.dumps({'task_id': task_id, 'executor_kind': 'YOLO'}, sort_keys=True).encode()
                _rid = (res.get("commit") if isinstance(res, dict) else None) or ("result-" + hashlib.sha256(_payload_str).hexdigest())"""

content = re.sub(
    r"                _rid = \(res.get\(\"commit\"\) if isinstance\(res, dict\) else None\) or \(task_id \+ \":r1\"\)",
    replacement_389,
    content
)

# For line 473:
replacement_473 = """                import hashlib
                _payload_str = json.dumps({'task_id': task_id, 'executor_kind': 'YOLO'}, sort_keys=True).encode()
                _rid = "result-" + hashlib.sha256(_payload_str).hexdigest()
                self.m["last_result"] = {"task": task_id, "result_id": _rid, "completed_at": time.time(), "yolo": res}"""

content = re.sub(
    r"                self.m\[\"last_result\"\] = \{\"task\": task_id, \"result_id\": task_id \+ \":r1\", \"completed_at\": time.time\(\), \"yolo\": res\}",
    replacement_473,
    content
)

with open("scripts/cannon_motor.py", "w") as f:
    f.write(content)
