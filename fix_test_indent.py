import sys, re

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

c = c.replace(
    "if config_path.exists() and 'orig_config' in locals():",
    "    if config_path.exists() and 'orig_config' in locals():"
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

