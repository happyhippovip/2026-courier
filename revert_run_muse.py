with open("scripts/cannon_yolo.py", "r") as f:
    content = f.read()

bad_block = '''if not eof:
            if (now - t0 > hard_s or now - last > idle_s):
                print(f"DEBUG TIMEOUT: t0={t0} last={last} now={now} hard_s={hard_s} idle_s={idle_s}", flush=True)
            why = "NOTAUS"'''
good_block = '''if not eof: why = "NOTAUS"'''

content = content.replace(bad_block, good_block)

with open("scripts/cannon_yolo.py", "w") as f:
    f.write(content)
