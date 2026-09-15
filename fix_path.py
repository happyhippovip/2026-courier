import json

with open("scripts/courier_control_plane.py", "r") as f:
    content = f.read()

content = content.replace(
    "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))",
    "sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))"
)

with open("scripts/courier_control_plane.py", "w") as f:
    f.write(content)
