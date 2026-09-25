import re
with open("tests/test_queue_independence.py", "r") as f:
    c = f.read()

# Replace hardcoded date with datetime.utcnow() formatted string!
c = c.replace(
    '"observed_at":"2026-09-18T22:05:45Z"',
    'f"\\"observed_at\\":\\"{__import__(\'datetime\').datetime.utcnow().strftime(\'%Y-%m-%dT%H:%M:%SZ\')}\\""'
)
# Wait, it's inside a dictionary initialization, so we can just replace the string literal!
c = re.sub(r'"observed_at":\s*"2026-09-18T22:05:45Z"', 'f"\\\"observed_at\\\":\\\"{__import__(\'datetime\').datetime.utcnow().strftime(\'%Y-%m-%dT%H:%M:%SZ\')}\\\""', c)
# Or better, just import datetime and replace it:
