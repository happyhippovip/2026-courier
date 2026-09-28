import re

with open("scripts/execute_all_finish_packets.py", "r") as f:
    content = f.read()

# Fix sed mess by checking out and applying regex cleanly
import subprocess
subprocess.run(["git", "checkout", "scripts/execute_all_finish_packets.py"])

with open("scripts/execute_all_finish_packets.py", "r") as f:
    content = f.read()

parts = content.split('print(f"Beginning execution of {len(tasks)} Mac Finish tasks...")')
header = parts[0]
footer = 'print(f"Beginning execution of {len(tasks)} Mac Finish tasks...")' + parts[1]

new_footer = "def execute_all():\n"
for line in footer.split("\n"):
    if line.strip() == "":
        new_footer += "\n"
    else:
        new_footer += "    " + line + "\n"

new_footer += "\nif __name__ == '__main__':\n    execute_all()\n"

with open("scripts/execute_all_finish_packets.py", "w") as f:
    f.write(header + new_footer)

