with open("scripts/courier_control_plane.py", "r") as f:
    content = f.read()

content = content.replace("                import os\n", "")

with open("scripts/courier_control_plane.py", "w") as f:
    f.write(content)
