import re
import datetime

fresh_date = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def update_file(filename):
    with open(filename, "r") as f:
        code = f.read()

    code = code.replace('"2026-09-17T12:00:00Z"', f'"{fresh_date}"')

    with open(filename, "w") as f:
        f.write(code)

update_file("tests/test_courier_continue.py")
