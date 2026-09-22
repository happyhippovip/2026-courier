import re

with open("tests/test_courier_continue.py", "r") as f:
    content = f.read()

# Replace hardcoded date with dynamic one
old_date = '"observed_at": "2026-09-18T22:06:15Z"'
new_date = '"observed_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")'

if old_date in content:
    content = content.replace(old_date, new_date)
    # also add import datetime if needed
    if "import datetime" not in content:
        content = "import datetime\n" + content
    with open("tests/test_courier_continue.py", "w") as f:
        f.write(content)
    print("Fixed test_courier_continue.py")
else:
    print("Date not found in file")

