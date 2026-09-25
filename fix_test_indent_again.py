import sys, re

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

c = c.replace(
    'pass # if config_path.exists() and \'orig_config\' in locals():\n        with open(config_path, "w") as cf:\n            json.dump(orig_config, cf)',
    'pass'
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

