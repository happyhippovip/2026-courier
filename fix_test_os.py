import sys, re

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

c = c.replace(
    'import json\n    import subprocess\n    import os',
    'import json\n    import subprocess'
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

