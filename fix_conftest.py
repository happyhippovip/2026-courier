import re

with open("tests/conftest.py", "r") as f:
    code = f.read()

code = code.replace(
    'if original_resolver is None:',
    'if True:'
)

with open("tests/conftest.py", "w") as f:
    f.write(code)
