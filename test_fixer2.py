import sys

with open("tests/test_tomato_two_torture.py", "r") as f:
    c = f.read()

c = c.replace(
    'pass\n    plist_path =',
    '    pass\n    plist_path ='
)

with open("tests/test_tomato_two_torture.py", "w") as f:
    f.write(c)

