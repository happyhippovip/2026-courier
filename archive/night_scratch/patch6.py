import sys

content = open("tests/test_tomato_two_torture.py").read()

content = content.replace(
    'stderr=subprocess.DEVNULL',
    'stderr=open("server_stderr.log", "w")'
).replace(
    'stdout=subprocess.DEVNULL',
    'stdout=open("server_stdout.log", "w")'
)

open("tests/test_tomato_two_torture.py", "w").write(content)
