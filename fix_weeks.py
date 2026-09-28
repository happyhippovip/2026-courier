import re
import sys

def fix_file(filename, week_num):
    with open(filename, "r") as f:
        content = f.read()

    split_str = f'print(f"Beginning execution of {{len(week{week_num}_blocks)}} Week {week_num} blocks...")'
    
    parts = content.split(split_str)
    if len(parts) == 1:
        print(f"Skipping {filename}, already fixed or pattern not found.")
        return
        
    header = parts[0]
    footer = split_str + parts[1]

    new_footer = "def execute_all():\n"
    for line in footer.split("\n"):
        if line.strip() == "":
            new_footer += "\n"
        else:
            new_footer += "    " + line + "\n"

    new_footer += "\nif __name__ == '__main__':\n    execute_all()\n"

    with open(filename, "w") as f:
        f.write(header + new_footer)
    print(f"Fixed {filename}")

fix_file("scripts/execute_week1_blocks.py", 1)
fix_file("scripts/execute_week2_blocks.py", 2)
fix_file("scripts/execute_week3_blocks.py", 3)
fix_file("scripts/execute_week4_blocks.py", 4)
