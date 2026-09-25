import re

with open("app/cannon/adapters.py", "r") as f:
    content = f.read()

replacement = """        payload_str = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        result_id = "result-" + hashlib.sha256(payload_str).hexdigest()"""

content = re.sub(
    r"        result_id = execution \+ ':r1'",
    replacement,
    content,
    flags=re.MULTILINE
)

with open("app/cannon/adapters.py", "w") as f:
    f.write(content)
