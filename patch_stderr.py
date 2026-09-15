from pathlib import Path

p = Path("scripts/courier_real_worker_adapters.py")
code = p.read_text()

old = '''                "summary": f"Windows execution. stdout: {res.stdout.strip()}",'''
new = '''                "summary": f"Windows execution. stdout: {res.stdout.strip()} stderr: {res.stderr.strip()}",'''

code = code.replace(old, new)
p.write_text(code)
print("Patched.")
