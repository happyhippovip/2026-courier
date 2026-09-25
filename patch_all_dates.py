import re
import glob
import datetime

now_str = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

for file in glob.glob("tests/**/*.py", recursive=True):
    with open(file, "r") as f:
        c = f.read()
    
    # We replace any "2026-09-XXTXX:XX:XXZ" with the current UTC time!
    new_c = re.sub(r'"2026-09-\d\dT\d\d:\d\d:\d\dZ"', f'"{now_str}"', c)
    if new_c != c:
        with open(file, "w") as f:
            f.write(new_c)
            print(f"Patched {file}")
