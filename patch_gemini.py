import re

with open("scripts/gemini_worker_adapter.py", "r") as f:
    code = f.read()

code = code.replace("stdout, stderr = process.communicate(timeout=60)", 
"""try:
        stdout, stderr = process.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()""")

with open("scripts/gemini_worker_adapter.py", "w") as f:
    f.write(code)
