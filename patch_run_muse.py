with open("scripts/cannon_yolo.py", "r") as f:
    content = f.read()

content = content.replace('if not eof: why = "NOTAUS"',
    'if not eof:\n            if (now - t0 > hard_s or now - last > idle_s):\n                print(f"DEBUG TIMEOUT: t0={t0} last={last} now={now} hard_s={hard_s} idle_s={idle_s}", flush=True)\n            why = "NOTAUS"')

with open("scripts/cannon_yolo.py", "w") as f:
    f.write(content)
