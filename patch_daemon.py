import re

with open("scripts/windows_worker/daemon.py", "r") as f:
    content = f.read()

old_logic = """
            try:
                body = e.read().decode('utf-8')
                if e.code in (200, 409) and '"ACK_DUPLICATE"' in body:
                    print(f"[Windows Worker] Result already acknowledged by server: {body}")
                    return
                elif e.code == 409 and '"CONTRADICTORY_DUPLICATE"' in body:
                    print(f"[Windows Worker] Result rejected as contradictory duplicate: {body}")
                    return
            except Exception:
                body = ""
"""

new_logic = """
            try:
                body = e.read().decode('utf-8')
                data = json.loads(body)
                if e.code in (200, 409) and data.get("status") == "ACK_DUPLICATE":
                    print(f"[Windows Worker] Result already acknowledged by server: {body}")
                    return
                elif e.code == 409 and data.get("reason") == "CONTRADICTORY_DUPLICATE":
                    print(f"[Windows Worker] Result rejected as contradictory duplicate: {body}")
                    return
            except Exception:
                body = ""
"""

content = content.replace(old_logic, new_logic)

with open("scripts/windows_worker/daemon.py", "w") as f:
    f.write(content)

