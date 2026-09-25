import os

files = [
    "scripts/headless_night.py",
    "app/cannon/adapters.py",
    "tests/test_headless_night_offline.py"
]

for file in files:
    with open(file, "r") as f:
        c = f.read()
    new_c = c.replace("--dangerously-skip-permissions", "--disable-approval")
    if new_c != c:
        with open(file, "w") as f:
            f.write(new_c)
            print(f"Reverted {file}")

