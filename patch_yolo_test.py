with open("tests/test_cannon_yolo.py", "r") as f:
    content = f.read()

content = content.replace('assert (k, d) == ("unknown", exp)',
    'print(f"DEBUG: mode={mode} exp={exp} k={k} d={d}"); assert (k, d) == ("unknown", exp)')

with open("tests/test_cannon_yolo.py", "w") as f:
    f.write(content)
