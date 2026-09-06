import re

with open("scripts/courier_real_worker_adapters.py", "r") as f:
    text = f.read()

bad = """            if s.startswith("/") or s.startswith("..") or "\\x00" in s:
            validated_scope.append(s)"""
good = """            if s.startswith("/") or s.startswith("..") or "\\x00" in s:
                continue
            validated_scope.append(s)"""
text = text.replace(bad, good)

bad_payload_in = """        task_id = task_envelope.get("task_id", task_hash[:16])
        requested_model = task_envelope.get("requested_model", "codex")
        requires_write = task_envelope.get("requires_write", False)"""

good_payload_in = """        task_id = task_envelope.get("task_id", task_hash[:16])
        payload_in = task_envelope.get("payload", {})
        requested_model = task_envelope.get("requested_model", "codex")
        requires_write = task_envelope.get("requires_write", False)"""
text = text.replace(bad_payload_in, good_payload_in)

with open("scripts/courier_real_worker_adapters.py", "w") as f:
    f.write(text)

