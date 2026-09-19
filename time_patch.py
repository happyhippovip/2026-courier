import re

with open("scripts/courier_continue.py") as f:
    text = f.read()

# Replace all print(f"DEBUG... with print(f"{time.time()} DEBUG...
text = re.sub(r'print\(f"DEBUG(.*?)', r'print(f"{time.time()} DEBUG\1', text)
text = re.sub(r'print\(f"\\n=== SUBMITTING', r'print(f"\\n{time.time()} === SUBMITTING', text)
text = re.sub(r'print\(f"\\n=== FINISHED', r'print(f"\\n{time.time()} === FINISHED', text)

with open("scripts/courier_continue.py", "w") as f:
    f.write(text)
